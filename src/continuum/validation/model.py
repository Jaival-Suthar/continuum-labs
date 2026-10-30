from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from continuum.core.models import Evidence, EvidenceStatus, GraphRelationship
from continuum.temporal.model import TemporalCheck


class ClaimClassification:
    """Canonical M9 classifications for proposed claims."""

    OBSERVED: ClassVar[str] = EvidenceStatus.OBSERVED
    DERIVED: ClassVar[str] = EvidenceStatus.DERIVED
    SUPPORTED_INFERENCE: ClassVar[str] = EvidenceStatus.SUPPORTED_INFERENCE
    CONTRADICTED: ClassVar[str] = EvidenceStatus.CONTRADICTED
    UNKNOWN: ClassVar[str] = EvidenceStatus.UNKNOWN
    ALL: ClassVar[frozenset[str]] = EvidenceStatus.ALL


@dataclass(frozen=True)
class Claim:
    """A deterministic representation of one proposed graph relationship."""

    subject: str
    relationship: str
    object: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.subject:
            raise ValueError("Claim.subject must not be empty")
        if not self.relationship:
            raise ValueError("Claim.relationship must not be empty")
        if not self.object:
            raise ValueError("Claim.object must not be empty")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.subject, self.relationship, self.object)


@dataclass(frozen=True)
class ClaimValidation:
    """Auditable output of the complete M9 validation pipeline."""

    claim: Claim
    classification: str
    graph_relationships: tuple[GraphRelationship, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    temporal_check: TemporalCheck | None = None
    contradictions: tuple[str, ...] = ()
    graph_valid: bool = False
    evidence_found: bool = False
    pipeline: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if self.classification not in ClaimClassification.ALL:
            raise ValueError(f"Unsupported claim classification: {self.classification}")

    @property
    def supported(self) -> bool:
        return self.classification in {
            ClaimClassification.OBSERVED,
            ClaimClassification.DERIVED,
            ClaimClassification.SUPPORTED_INFERENCE,
        }

    @property
    def status(self) -> str:
        return self.classification

    @property
    def insufficient_evidence(self) -> bool:
        return self.classification == ClaimClassification.UNKNOWN

    @property
    def message(self) -> str:
        if self.classification == ClaimClassification.UNKNOWN:
            return "Insufficient evidence."
        if self.classification == ClaimClassification.CONTRADICTED:
            return "Claim contradicted by graph, evidence, or temporal validation."
        return self.reason
