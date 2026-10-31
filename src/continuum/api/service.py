from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from continuum.core import (
    EvidenceStatus,
    InvestigationResult,
)
from continuum.core import (
    Hypothesis as StateHypothesis,
)
from continuum.graph.client import GraphClient
from continuum.graph.loader import WorldLoader
from continuum.hypothesis import CompetitionOutcome, path_id
from continuum.investigator import Investigator
from continuum.report import GroundedReportBuilder
from domains.software.world import SOFTWARE_WORLD
from domains.supply_chain.world import SUPPLY_CHAIN_WORLD

WORLDS = {
    SOFTWARE_WORLD.name: SOFTWARE_WORLD,
    SUPPLY_CHAIN_WORLD.name: SUPPLY_CHAIN_WORLD,
}


class InvestigationService:
    """M17 application service.

    This layer is deliberately a projection boundary. Investigation, temporal
    validation, provenance resolution, ranking and hypothesis competition all
    remain in the existing backend packages. The browser receives only data
    needed to render and inspect an investigation.
    """

    def __init__(self, graph: GraphClient, *, storage_dir: Path | None = None):
        self.graph = graph
        self.storage_dir = storage_dir or Path("artifacts/m17/investigations")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._investigations: dict[str, dict[str, Any]] = {}
        self._load_index()

    def health(self) -> dict[str, Any]:
        self.graph.ping()
        return {
            "status": "ok",
            "graph": self.graph.config.graph_name,
            "falkordb": "connected",
        }

    def worlds(self) -> list[dict[str, str]]:
        return [{"id": name, "name": name.replace("-", " ").title()} for name in WORLDS]

    def create(
        self, *, question: str, domain: str, target_id: str | None = None
    ) -> dict[str, Any]:
        question = question.strip()
        domain = domain.strip().lower()
        if not question:
            raise ValueError("question must not be empty")
        if domain not in WORLDS:
            raise ValueError(f"unsupported domain: {domain}")

        with self._lock:
            world = WORLDS[domain]
            WorldLoader(self.graph).load(world, reset=True)
            investigator = Investigator(self.graph, world)
            result = investigator.investigate(question, world=world)
            if target_id is not None and result.target != target_id:
                raise ValueError(
                    f"target_id {target_id!r} does not match the investigated target {result.target!r}"
                )

            # Hypothesis competition consumes actual graph-derived paths. We do
            # not invent semantic claims: each hypothesis explicitly represents
            # one recovered path, and the deterministic evaluator owns scoring.
            state = investigator.start_investigation(
                question,
                target_id=result.target,
            )
            state.merge_result(result, operation="m17_investigate")
            candidates = [
                p for p in result.candidate_paths if p.temporally_valid is not False
            ]
            for index, path in enumerate(candidates[:3], start=1):
                state.add_hypothesis(
                    StateHypothesis(
                        id=f"H{index}",
                        description=f"Graph-derived path: {' → '.join(path.node_ids)}",
                        candidate_path_ids=(path_id(path),),
                        evidence_ids=tuple(e.id for e in path.evidence),
                    )
                )
            competition = (
                investigator.compete_hypotheses(state) if state.hypotheses else None
            )
            if competition is not None:
                state.extensions["hypothesis_competition"] = competition.as_dict()
                report = GroundedReportBuilder().from_state(state)
            else:
                report = GroundedReportBuilder().from_result(result)

            investigation_id = f"inv-{uuid.uuid4().hex[:12]}"
            payload = self._serialize_investigation(
                investigation_id,
                domain,
                result,
                competition.as_dict() if competition else None,
                report.as_dict(),
            )
            self._investigations[investigation_id] = payload
            self._persist(investigation_id, payload)
            return payload

    def get(self, investigation_id: str) -> dict[str, Any]:
        payload = self._investigations.get(investigation_id)
        if payload is None:
            raise KeyError(investigation_id)
        return payload

    def graph_projection(self, investigation_id: str) -> dict[str, Any]:
        item = self.get(investigation_id)
        return {
            "nodes": item["graph"]["nodes"],
            "edges": item["graph"]["edges"],
            "paths": item["paths"],
        }

    def evidence(self, investigation_id: str, evidence_id: str) -> dict[str, Any]:
        item = self.get(investigation_id)
        for evidence in item["evidence"]:
            if evidence["id"] == evidence_id:
                return evidence
        raise KeyError(evidence_id)

    def _serialize_investigation(
        self,
        investigation_id: str,
        domain: str,
        result: InvestigationResult,
        competition: dict[str, Any] | None,
        report: dict[str, Any],
    ) -> dict[str, Any]:
        paths = [self._path_dict(path) for path in result.candidate_paths]
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}
        for path in result.candidate_paths:
            for record in path.node_records:
                if isinstance(record, dict) and record.get("id"):
                    nodes[str(record["id"])] = self._jsonable(record)
            for index, record in enumerate(path.edge_records):
                if not isinstance(record, dict):
                    continue
                edge_id = record.get("edge_id") or (
                    path.edge_ids[index] if index < len(path.edge_ids) else None
                )
                if edge_id:
                    edges[str(edge_id)] = self._jsonable(record)

            # The investigator's path records are authoritative; relationships
            # and endpoints are retained even when a provider omits properties.
            for index, node_id in enumerate(path.node_ids):
                nodes.setdefault(node_id, {"id": node_id, "name": node_id})
                if index < len(path.relationships):
                    edge_id = path.edge_ids[index] or f"{path_id(path)}:{index}"
                    edges.setdefault(
                        edge_id,
                        {
                            "edge_id": edge_id,
                            "source_id": node_id,
                            "target_id": path.node_ids[index + 1],
                            "relationship": path.relationships[index],
                            "evidence_status": EvidenceStatus.OBSERVED
                            if index < path.supporting_relationship_count
                            else EvidenceStatus.UNKNOWN,
                        },
                    )

        return {
            "id": investigation_id,
            "domain": domain,
            "question": result.question,
            "target": result.target,
            "status": self._status(result, competition),
            "created_at": datetime.now().astimezone().isoformat(),
            "trace": list(result.trace),
            "paths": paths,
            "graph": {"nodes": list(nodes.values()), "edges": list(edges.values())},
            "evidence": [self._evidence_dict(item) for item in result.evidence],
            "temporal_validation": list(result.temporal_checks),
            "contradictions": list(result.contradictions),
            "unknowns": list(result.gaps),
            "ranked_paths": [self._ranking_dict(item) for item in result.ranked_paths],
            "hypotheses": (competition or {}).get("hypotheses", []),
            "competition": competition,
            "verdict": (competition or {}).get("verdict") or result.verdict,
            "report": report,
        }

    @staticmethod
    def _status(result: InvestigationResult, competition: dict[str, Any] | None) -> str:
        if result.target is None:
            return "NO_TARGET"
        if (
            competition
            and competition.get("outcome") == CompetitionOutcome.INSUFFICIENT
        ):
            return "INSUFFICIENT_EVIDENCE"
        if competition and competition.get("outcome") == CompetitionOutcome.AMBIGUOUS:
            return "AMBIGUOUS"
        if competition and competition.get("outcome") == CompetitionOutcome.WINNER:
            return "COMPLETED"
        return "COMPLETED"

    @staticmethod
    def _path_dict(path: Any) -> dict[str, Any]:
        return {
            "id": path_id(path),
            "node_ids": list(path.node_ids),
            "relationships": list(path.relationships),
            "edge_ids": list(path.edge_ids),
            "temporal_status": path.temporal_status,
            "temporal_reason": path.temporal_reason,
            "temporally_valid": path.temporally_valid,
            "evidence_ids": [e.id for e in path.evidence],
            "supporting_relationship_count": path.supporting_relationship_count,
            "conflicting_relationship_count": path.conflicting_relationship_count,
            "missing_evidence_count": path.missing_evidence_count,
            "direction": path.direction,
        }

    @staticmethod
    def _evidence_dict(item: Any) -> dict[str, Any]:
        return {
            "id": item.id,
            "source_id": item.source_id,
            "status": item.status,
            "observed_at": (
                item.observed_at.isoformat()
                if hasattr(item.observed_at, "isoformat")
                else item.observed_at
                if item.observed_at
                else None
            ),
            "record": item.record,
            "span": item.span,
            "metadata": item.metadata,
        }

    @staticmethod
    def _ranking_dict(item: Any) -> dict[str, Any]:
        return {
            "path_id": path_id(item.path),
            "temporal_validity": item.temporal_validity,
            "path_length": item.path_length,
            "evidence_count": item.evidence_count,
            "supporting_relationship_count": item.supporting_relationship_count,
            "conflicting_relationship_count": item.conflicting_relationship_count,
            "missing_evidence_count": item.missing_evidence_count,
            "rank_key": list(item.rank_key),
        }

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if is_dataclass(value):
            return {
                k: InvestigationService._jsonable(v) for k, v in asdict(value).items()
            }
        if isinstance(value, dict):
            return {str(k): InvestigationService._jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [InvestigationService._jsonable(v) for v in value]
        return value

    def _persist(self, investigation_id: str, payload: dict[str, Any]) -> None:
        path = self.storage_dir / f"{investigation_id}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _load_index(self) -> None:
        for path in sorted(self.storage_dir.glob("inv-*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("id"):
                    self._investigations[str(payload["id"])] = payload
            except (OSError, ValueError, TypeError):
                # Corrupt persisted state is not silently used. The file remains
                # on disk for diagnosis and simply isn't exposed as an API item.
                continue
