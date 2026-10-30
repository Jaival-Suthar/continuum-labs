from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from continuum.baseline import BaselineRunner, build_corpus
from continuum.core.models import InvestigationPath
from continuum.evaluation.cases import EvaluationDataset
from continuum.evaluation.metrics import (
    continuum_evidence_metrics,
    efficiency_metrics,
    evidence_metrics,
    path_recovery,
    temporal_metrics,
)
from continuum.evaluation.model import (
    BaselineCaseResult,
    ContinuumCaseResult,
    EvaluationCase,
    EvaluationResult,
)
from continuum.graph.client import GraphClient
from continuum.graph.loader import WorldLoader
from continuum.investigator import Investigator


@dataclass
class CountingGraphClient:
    """Transparent proxy that counts actual graph operations."""

    client: GraphClient
    reads: int = 0
    writes: int = 0

    def read(self, cypher: str, params: dict[str, Any] | None = None):
        self.reads += 1
        return self.client.read(cypher, params)

    def query(self, cypher: str, params: dict[str, Any] | None = None):
        self.writes += 1
        return self.client.query(cypher, params)

    def reset(self) -> None:
        self.writes += 1
        self.client.reset()

    def ping(self) -> bool:
        return self.client.ping()


class ControlledEvaluationRunner:
    """Run M12 and Continuum on exactly the same controlled case data."""

    def __init__(
        self,
        graph: GraphClient,
        dataset: EvaluationDataset,
        *,
        top_k: int = 8,
        max_hops: int = 6,
    ) -> None:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")
        self.graph = CountingGraphClient(graph)
        self.dataset = dataset
        self.top_k = top_k
        self.max_hops = max_hops

    def seed(self) -> None:
        WorldLoader(self.graph).load(self.dataset.world, reset=True)

    def run_case(self, case: EvaluationCase) -> EvaluationResult:
        if case not in self.dataset.cases:
            raise ValueError(f"case {case.case_id!r} does not belong to this dataset")

        baseline = BaselineRunner(build_corpus(self.dataset.world))
        retrieved = baseline.retrieve(case.question, top_k=self.top_k)
        recovered_edges = tuple(
            (
                str(item.document.metadata["source_id"]),
                str(item.document.metadata["relationship"]),
                str(item.document.metadata["target_id"]),
                str(item.document.metadata["edge_id"]),
            )
            for item in retrieved
            if item.document.metadata.get("kind") == "edge"
        )
        retrieved_paths = _recover_paths(
            recovered_edges, target_id=case.ground_truth_path[-1]
        )
        baseline_edge_ids = tuple(item[3] for item in recovered_edges)
        baseline_evidence_by_edge = {
            edge_id: tuple(
                source_id
                for item in retrieved
                if item.document.metadata.get("kind") == "edge"
                and item.document.metadata.get("edge_id") == edge_id
                for source_id in item.document.source_ids
            )
            for edge_id in baseline_edge_ids
        }
        baseline_evidence = evidence_metrics(
            case.expected_edge_evidence,
            baseline_edge_ids,
            baseline_evidence_by_edge,
        )
        baseline_path_metrics = path_recovery(case.ground_truth_path, retrieved_paths)
        node_timestamps = {
            node.id: node.timestamp
            for node in self.dataset.world.data.nodes()
            if node.timestamp is not None
        }
        baseline_temporal = temporal_metrics(
            case.temporal_constraints,
            node_timestamps,
            baseline_path_metrics.best_recovered_path or None,
        )
        baseline_result = BaselineCaseResult(
            retrieved_ids=tuple(item.document.id for item in retrieved),
            retrieved_source_ids=tuple(
                dict.fromkeys(
                    source_id
                    for item in retrieved
                    for source_id in item.document.source_ids
                )
            ),
            retrieved_edge_ids=baseline_edge_ids,
            recovered_edges=recovered_edges,
            answer=None,
            model=None,
            path_recovery=baseline_path_metrics,
            evidence=baseline_evidence,
            temporal=baseline_temporal,
        )

        start_reads = self.graph.reads
        start_writes = self.graph.writes
        started = time.perf_counter()
        investigator = Investigator(self.graph, self.dataset.world)
        investigation = investigator.investigate(case.question)
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        candidate_paths = tuple(path.node_ids for path in investigation.candidate_paths)
        best_path = _best_path(investigation.candidate_paths)
        continuum_path_metrics = path_recovery(case.ground_truth_path, candidate_paths)
        continuum_evidence = continuum_evidence_metrics(
            best_path, case.expected_edge_evidence
        )
        temporal = temporal_metrics(
            case.temporal_constraints,
            node_timestamps,
            continuum_path_metrics.best_recovered_path or None,
        )
        reads = self.graph.reads - start_reads
        writes = self.graph.writes - start_writes
        efficiency = efficiency_metrics(
            graph_reads=reads,
            graph_writes=writes,
            investigation_steps=len(investigation.trace),
            nodes_explored=len(set(investigation.discovered_nodes)),
            edges_explored=len(set(investigation.discovered_edges)),
            elapsed_ms=elapsed_ms,
        )
        continuum_result = ContinuumCaseResult(
            target=investigation.target,
            candidate_paths=candidate_paths,
            evidence_ids=tuple(item.id for item in investigation.evidence),
            path_recovery=continuum_path_metrics,
            evidence=continuum_evidence,
            temporal=temporal,
            efficiency=efficiency,
            trace=tuple(investigation.trace),
        )

        return EvaluationResult(
            case_id=case.case_id,
            domain=case.domain,
            question=case.question,
            ground_truth_path=case.ground_truth_path,
            ground_truth_edge_ids=case.ground_truth_edge_ids,
            baseline=baseline_result,
            continuum=continuum_result,
            temporal_constraints=case.temporal_constraints,
            expected_answer=case.expected_answer,
            metadata={"top_k": self.top_k, "max_hops": self.max_hops},
        )

    def run_all(
        self, cases: Iterable[EvaluationCase] | None = None
    ) -> tuple[EvaluationResult, ...]:
        selected = tuple(cases or self.dataset.cases)
        if not selected:
            raise ValueError("at least one evaluation case is required")
        return tuple(self.run_case(case) for case in selected)


def _recover_paths(
    edges: tuple[tuple[str, str, str, str], ...], *, target_id: str
) -> tuple[tuple[str, ...], ...]:
    """Recover chains from retrieved edge records only; never queries the graph."""
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for source, _relationship, target, _edge_id in edges:
        adjacency.setdefault(source, []).append((target, source))

    results: list[tuple[str, ...]] = []
    max_hops = len(edges)

    def visit(current: str, path: tuple[str, ...]) -> None:
        if len(path) > max_hops + 1:
            return
        if current == target_id and len(path) > 1:
            results.append(path)
            return
        for target, _ in adjacency.get(current, []):
            if target in path:
                continue
            visit(target, (*path, target))

    for source in adjacency:
        visit(source, (source,))
    return tuple(dict.fromkeys(results))


def _best_path(paths: Iterable[InvestigationPath]) -> InvestigationPath | None:
    items = tuple(paths)
    if not items:
        return None
    return max(
        items,
        key=lambda path: (
            path.temporally_valid is True,
            path.supporting_relationship_count,
            len(path.evidence),
            -path.missing_evidence_count,
            -path.hop_count,
            path.node_ids,
        ),
    )
