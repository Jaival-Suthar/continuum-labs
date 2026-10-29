from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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
    """Domain-independent representation of a relationship."""

    source_id: str
    relationship: str
    target_id: str
    timestamp: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    evidence_source_ids: tuple[str, ...] = ()
    properties: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id or not self.target_id:
            raise ValueError("GraphEdge endpoints must not be empty")
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValueError("valid_from must be <= valid_until")


@dataclass
class Source:
    id: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Evidence:
    source_id: str
    status: str
    observed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphRelationship:
    source_id: str
    relationship: str
    target_id: str
    evidence_source_ids: tuple[str, ...] = ()


@dataclass
class InvestigationResult:
    question: str
    paths: list[list[str]] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    verdict: str | None = None
    trace: list[str] = field(default_factory=list)
