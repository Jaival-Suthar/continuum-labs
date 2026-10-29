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

    @property
    def paths(self) -> list[list[str]]:
        """Compatibility view retained from the pre-M6 result model."""
        return [list(path.node_ids) for path in self.candidate_paths]
