from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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
