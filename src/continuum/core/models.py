from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar


class EvidenceStatus:
    """Canonical evidence states used by the provenance contract."""

    OBSERVED: ClassVar[str] = "OBSERVED"
    DERIVED: ClassVar[str] = "DERIVED"
    SUPPORTED_INFERENCE: ClassVar[str] = "SUPPORTED_INFERENCE"
    CONTRADICTED: ClassVar[str] = "CONTRADICTED"
    UNKNOWN: ClassVar[str] = "UNKNOWN"
    ALL: ClassVar[frozenset[str]] = frozenset(
        {OBSERVED, DERIVED, SUPPORTED_INFERENCE, CONTRADICTED, UNKNOWN}
    )


def _canonical_edge_payload(
    source_id: str,
    relationship: str,
    target_id: str,
    timestamp: datetime | None,
    valid_from: datetime | None,
    valid_until: datetime | None,
    evidence_source_ids: tuple[str, ...],
) -> str:
    payload = {
        "source_id": source_id,
        "relationship": relationship,
        "target_id": target_id,
        "timestamp": timestamp.isoformat() if timestamp else None,
        "valid_from": valid_from.isoformat() if valid_from else None,
        "valid_until": valid_until.isoformat() if valid_until else None,
        "evidence_source_ids": sorted(evidence_source_ids),
    }
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


@dataclass(frozen=True)
class GraphNode:
    """Domain-independent representation of a graph node."""

    id: str
    label: str
    name: str
    timestamp: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    observed_at: datetime | None = None
    properties: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("GraphNode.id must not be empty")
        if not self.name:
            raise ValueError("GraphNode.name must not be empty")
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValueError("valid_from must be <= valid_until")


@dataclass(frozen=True)
class GraphEdge:
    """Domain-independent relationship with stable identity and provenance."""

    source_id: str
    relationship: str
    target_id: str
    timestamp: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    evidence_source_ids: tuple[str, ...] = ()
    properties: dict[str, Any] = field(default_factory=dict)
    edge_id: str | None = None

    def __post_init__(self) -> None:
        if not self.source_id or not self.target_id:
            raise ValueError("GraphEdge endpoints must not be empty")
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValueError("valid_from must be <= valid_until")
        if self.edge_id is not None and not self.edge_id:
            raise ValueError("GraphEdge.edge_id must not be empty")
        if len(set(self.evidence_source_ids)) != len(self.evidence_source_ids):
            raise ValueError("GraphEdge.evidence_source_ids must be unique")
        if self.evidence_status not in EvidenceStatus.ALL:
            raise ValueError(f"Unsupported evidence status: {self.evidence_status}")

    @property
    def stable_id(self) -> str:
        if self.edge_id:
            return self.edge_id
        canonical = _canonical_edge_payload(
            self.source_id,
            self.relationship,
            self.target_id,
            self.timestamp,
            self.valid_from,
            self.valid_until,
            self.evidence_source_ids,
        )
        return f"edge-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]}"

    @property
    def evidence_status(self) -> str:
        explicit = self.properties.get("evidence_status")
        if explicit is not None:
            return str(explicit)
        return (
            EvidenceStatus.OBSERVED
            if self.evidence_source_ids
            else EvidenceStatus.UNKNOWN
        )


@dataclass(frozen=True)
class Source:
    """Inspectable source record used to support graph relationships."""

    id: str
    name: str
    record: str | None = None
    span: str | None = None
    observed_at: datetime | None = None
    status: str = EvidenceStatus.OBSERVED
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Source.id must not be empty")
        if not self.name:
            raise ValueError("Source.name must not be empty")
        if self.status not in EvidenceStatus.ALL:
            raise ValueError(f"Unsupported source status: {self.status}")


@dataclass(frozen=True)
class Evidence:
    """Resolved evidence attached to a graph relationship."""

    id: str
    source_id: str
    status: str
    observed_at: datetime | None = None
    record: str | None = None
    span: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Evidence.id must not be empty")
        if not self.source_id:
            raise ValueError("Evidence.source_id must not be empty")
        if self.status not in EvidenceStatus.ALL:
            raise ValueError(f"Unsupported evidence status: {self.status}")


@dataclass(frozen=True)
class GraphRelationship:
    """A relationship plus all provenance required to audit it."""

    source_id: str
    relationship: str
    target_id: str
    evidence_source_ids: tuple[str, ...] = ()
    edge_id: str | None = None
    timestamp: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    evidence_status: str = EvidenceStatus.UNKNOWN
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class InvestigationPath:
    """One graph-derived candidate explanation, enriched deterministically."""

    node_ids: tuple[str, ...]
    relationships: tuple[str, ...]
    edge_ids: tuple[str | None, ...]
    temporal_status: str
    temporal_reason: str
    evidence: tuple[Evidence, ...] = ()
    supporting_relationship_count: int = 0
    conflicting_relationship_count: int = 0
    missing_evidence_count: int = 0
    direction: str = "forward"
    node_records: tuple[dict[str, Any], ...] = ()
    edge_records: tuple[dict[str, Any], ...] = ()

    @property
    def hop_count(self) -> int:
        return len(self.relationships)

    @property
    def temporally_valid(self) -> bool | None:
        return {"VALID": True, "INVALID": False, "UNKNOWN": None}.get(
            self.temporal_status
        )


@dataclass(frozen=True)
class PathRanking:
    """Transparent deterministic ranking signals; no invented confidence."""

    path: InvestigationPath
    temporal_validity: int
    path_length: int
    evidence_count: int
    supporting_relationship_count: int
    conflicting_relationship_count: int
    missing_evidence_count: int
    rank_key: tuple[int, int, int, int, int, int]


@dataclass(frozen=True)
class Hypothesis:
    """Persistent investigative hypothesis state.

    M7 stores hypotheses and their accumulated references; it does not score
    or select between them. Hypothesis competition remains an M10 concern.
    """

    id: str
    description: str
    candidate_path_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()
    temporal_constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Hypothesis.id must not be empty")
        if not self.description:
            raise ValueError("Hypothesis.description must not be empty")
        for field_name in (
            "candidate_path_ids",
            "evidence_ids",
            "contradictions",
            "gaps",
            "temporal_constraints",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"Hypothesis.{field_name} must be unique")


@dataclass(frozen=True)
class InvestigationStep:
    """One deterministic operation performed against an investigation state."""

    operation: str
    input: dict[str, Any]
    result: InvestigationResult
    state_version: int
    added_nodes: tuple[str, ...] = ()
    added_edges: tuple[str, ...] = ()
    added_path_count: int = 0
    added_evidence_count: int = 0
    added_contradiction_count: int = 0
    added_gap_count: int = 0
    added_temporal_constraint_count: int = 0

    def __post_init__(self) -> None:
        if not self.operation:
            raise ValueError("InvestigationStep.operation must not be empty")
        if self.state_version < 1:
            raise ValueError("InvestigationStep.state_version must be >= 1")
        for field_name in (
            "added_path_count",
            "added_evidence_count",
            "added_contradiction_count",
            "added_gap_count",
            "added_temporal_constraint_count",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be >= 0")


@dataclass
class InvestigationState:
    """Cumulative state for a multi-step deterministic investigation.

    The state is deliberately separate from ``InvestigationResult``. M6
    describes what one deterministic operation discovered; M7 retains those
    discoveries so later operations consume the same investigation rather
    than starting from an empty result.
    """

    question: str
    target: str | None = None
    hypotheses: list[Hypothesis] = field(default_factory=list)
    explored_nodes: set[str] = field(default_factory=set)
    explored_edges: set[str] = field(default_factory=set)
    candidate_paths: list[InvestigationPath] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    temporal_constraints: list[str] = field(default_factory=list)
    history: list[InvestigationStep] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("InvestigationState.question must not be empty")
        self._deduplicate_collections()

    @property
    def version(self) -> int:
        """Number of completed investigation operations."""
        return len(self.history)

    @property
    def steps(self) -> list[InvestigationStep]:
        """Compatibility/readability alias for the investigation history."""
        return self.history

    def add_hypothesis(self, hypothesis: Hypothesis) -> None:
        """Add or merge one hypothesis by stable id."""
        for index, existing in enumerate(self.hypotheses):
            if existing.id != hypothesis.id:
                continue
            self.hypotheses[index] = Hypothesis(
                id=existing.id,
                description=existing.description,
                candidate_path_ids=_unique(
                    existing.candidate_path_ids + hypothesis.candidate_path_ids
                ),
                evidence_ids=_unique(existing.evidence_ids + hypothesis.evidence_ids),
                contradictions=_unique(
                    existing.contradictions + hypothesis.contradictions
                ),
                gaps=_unique(existing.gaps + hypothesis.gaps),
                temporal_constraints=_unique(
                    existing.temporal_constraints + hypothesis.temporal_constraints
                ),
            )
            return
        self.hypotheses.append(hypothesis)

    def apply_result(
        self,
        operation: str,
        result: InvestigationResult,
        *,
        input: dict[str, Any] | None = None,
    ) -> InvestigationStep:
        """Merge one M6 result into this state and record the operation.

        All merges are deterministic and idempotent. Re-applying the same
        result cannot duplicate nodes, edges, paths, evidence, contradictions,
        gaps, or temporal constraints. History still records the operation
        because two executions are two real investigation steps.
        """
        if result.question != self.question:
            raise ValueError(
                "InvestigationResult.question does not match "
                "InvestigationState.question"
            )
        before_nodes = set(self.explored_nodes)
        before_edges = set(self.explored_edges)
        before_paths = {self._path_key(path) for path in self.candidate_paths}
        before_evidence = {item.id for item in self.evidence}
        before_contradictions = set(self.contradictions)
        before_gaps = set(self.gaps)
        before_constraints = set(self.temporal_constraints)

        if result.target is not None:
            self.target = result.target

        self.explored_nodes.update(result.discovered_nodes)
        self.explored_edges.update(result.discovered_edges)

        for path in result.candidate_paths:
            self._merge_path(path)

        for item in result.evidence:
            self._merge_evidence(item)

        self.contradictions = _unique_list(self.contradictions + result.contradictions)
        self.gaps = _unique_list(self.gaps + result.gaps)
        self.temporal_constraints = _unique_list(
            self.temporal_constraints + result.temporal_checks
        )

        self._deduplicate_collections()

        added_nodes = tuple(sorted(self.explored_nodes - before_nodes))
        added_edges = tuple(sorted(self.explored_edges - before_edges))
        added_paths = len(
            {self._path_key(path) for path in self.candidate_paths} - before_paths
        )
        added_evidence = len({item.id for item in self.evidence} - before_evidence)
        added_contradictions = len(set(self.contradictions) - before_contradictions)
        added_gaps = len(set(self.gaps) - before_gaps)
        added_constraints = len(set(self.temporal_constraints) - before_constraints)

        step = InvestigationStep(
            operation=operation,
            input=dict(input or {}),
            result=result,
            state_version=self.version + 1,
            added_nodes=added_nodes,
            added_edges=added_edges,
            added_path_count=added_paths,
            added_evidence_count=added_evidence,
            added_contradiction_count=added_contradictions,
            added_gap_count=added_gaps,
            added_temporal_constraint_count=added_constraints,
        )
        self.history.append(step)
        return step

    def merge_result(
        self,
        result: InvestigationResult,
        *,
        operation: str = "investigate",
        input: dict[str, Any] | None = None,
    ) -> InvestigationStep:
        """Explicit alias for callers that think in terms of result merging."""
        return self.apply_result(operation, result, input=input)

    def _merge_path(self, path: InvestigationPath) -> None:
        key = self._path_key(path)
        if not any(
            self._path_key(existing) == key for existing in self.candidate_paths
        ):
            self.candidate_paths.append(path)

        self.explored_nodes.update(path.node_ids)
        for source_id, target_id, relationship, edge_id in zip(
            path.node_ids[:-1],
            path.node_ids[1:],
            path.relationships,
            path.edge_ids,
            strict=True,
        ):
            self.explored_edges.add(
                edge_id or f"{source_id}|{relationship}|{target_id}"
            )

    def _merge_evidence(self, evidence: Evidence) -> None:
        if not any(existing.id == evidence.id for existing in self.evidence):
            self.evidence.append(evidence)

    @staticmethod
    def _path_key(path: InvestigationPath) -> tuple[Any, ...]:
        return (path.node_ids, path.relationships, path.edge_ids)

    def _deduplicate_collections(self) -> None:
        self.hypotheses = _unique_by_id(self.hypotheses)
        unique_paths: dict[tuple[Any, ...], InvestigationPath] = {}
        for path in self.candidate_paths:
            unique_paths.setdefault(self._path_key(path), path)
        self.candidate_paths = list(unique_paths.values())
        self.evidence = _unique_by_id(self.evidence)
        self.contradictions = _unique_list(self.contradictions)
        self.gaps = _unique_list(self.gaps)
        self.temporal_constraints = _unique_list(self.temporal_constraints)


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _unique_list(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _unique_by_id(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        identifier = getattr(value, "id", None)
        if identifier is None or identifier in seen:
            continue
        seen.add(identifier)
        result.append(value)
    return result


@dataclass
class InvestigationResult:
    """Complete deterministic investigation output before any LLM synthesis."""

    question: str
    target: str | None = None
    candidate_paths: list[InvestigationPath] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    temporal_checks: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    ranked_paths: list[PathRanking] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
    verdict: str | None = None
    discovered_nodes: list[str] = field(default_factory=list)
    discovered_edges: list[str] = field(default_factory=list)

    @property
    def paths(self) -> list[list[str]]:
        """Compatibility view retained from the pre-M6 result model."""
        return [list(path.node_ids) for path in self.candidate_paths]
