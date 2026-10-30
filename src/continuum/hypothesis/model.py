from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, ClassVar

from continuum.core import Evidence, InvestigationPath
from continuum.validation import ClaimValidation


class TemporalValidity:
    VALID: ClassVar[str] = "VALID"
    INVALID: ClassVar[str] = "INVALID"
    UNKNOWN: ClassVar[str] = "UNKNOWN"
    ALL: ClassVar[frozenset[str]] = frozenset({VALID, INVALID, UNKNOWN})


class PathQuality:
    STRONG: ClassVar[str] = "STRONG"
    MODERATE: ClassVar[str] = "MODERATE"
    WEAK: ClassVar[str] = "WEAK"
    ALL: ClassVar[frozenset[str]] = frozenset({STRONG, MODERATE, WEAK})


class CompetitionOutcome:
    WINNER: ClassVar[str] = "WINNER"
    AMBIGUOUS: ClassVar[str] = "AMBIGUOUS"
    INSUFFICIENT: ClassVar[str] = "INSUFFICIENT"
    ALL: ClassVar[frozenset[str]] = frozenset({WINNER, AMBIGUOUS, INSUFFICIENT})


@dataclass(frozen=True)
class Hypothesis:
    """Deterministic M10 representation of one competing explanation.

    This is an evaluated object, not an LLM string. Every populated evidence,
    contradiction, temporal, and path field is derived from graph paths and the
    M9 claim-validation boundary.
    """

    id: str
    claim: str
    supporting_evidence: tuple[Evidence, ...] = ()
    contradictions: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    temporal_validity: str = TemporalValidity.UNKNOWN
    candidate_paths: tuple[InvestigationPath, ...] = ()
    path_quality: str = PathQuality.WEAK
    score: int = 0
    claim_validations: tuple[ClaimValidation, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Hypothesis.id must not be empty")
        if not self.claim.strip():
            raise ValueError("Hypothesis.claim must not be empty")
        if self.temporal_validity not in TemporalValidity.ALL:
            raise ValueError(f"Unsupported temporal validity: {self.temporal_validity}")
        if self.path_quality not in PathQuality.ALL:
            raise ValueError(f"Unsupported path quality: {self.path_quality}")

    @property
    def support_count(self) -> int:
        return sum(validation.supported for validation in self.claim_validations)

    @property
    def contradiction_count(self) -> int:
        return len(self.contradictions)

    @property
    def missing_evidence_count(self) -> int:
        return len(self.missing_evidence)

    @property
    def valid_path_count(self) -> int:
        return sum(path.temporally_valid is True for path in self.candidate_paths)

    @property
    def invalid_path_count(self) -> int:
        return sum(path.temporally_valid is False for path in self.candidate_paths)

    @property
    def plausible(self) -> bool:
        """A hypothesis is plausible only with positive support and no contradiction."""
        return (
            self.support_count > 0
            and self.contradiction_count == 0
            and self.missing_evidence_count == 0
            and self.valid_path_count > 0
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "claim": self.claim,
            "supporting_evidence": [item.id for item in self.supporting_evidence],
            "contradictions": list(self.contradictions),
            "missing_evidence": list(self.missing_evidence),
            "temporal_validity": self.temporal_validity,
            "candidate_paths": [path_id(path) for path in self.candidate_paths],
            "path_quality": self.path_quality,
            "score": self.score,
            "support_count": self.support_count,
            "contradiction_count": self.contradiction_count,
            "missing_evidence_count": self.missing_evidence_count,
            "valid_path_count": self.valid_path_count,
            "invalid_path_count": self.invalid_path_count,
            "plausible": self.plausible,
        }


@dataclass(frozen=True)
class HypothesisCompetitionResult:
    """Complete deterministic competition result."""

    outcome: str
    hypotheses: tuple[Hypothesis, ...]
    winner_ids: tuple[str, ...] = ()
    reason: str = ""
    score_formula: str = (
        "score = support + temporal + path_quality - contradiction - missing_evidence"
    )

    def __post_init__(self) -> None:
        if self.outcome not in CompetitionOutcome.ALL:
            raise ValueError(f"Unsupported competition outcome: {self.outcome}")
        if len(self.winner_ids) != len(set(self.winner_ids)):
            raise ValueError("winner_ids must be unique")

    @property
    def verdict(self) -> str:
        if self.outcome == CompetitionOutcome.WINNER:
            return f"{self.winner_ids[0]} best supported"
        if self.outcome == CompetitionOutcome.AMBIGUOUS:
            return f"{', '.join(self.winner_ids)} remain plausible"
        return "Insufficient evidence"

    def as_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "winner_ids": list(self.winner_ids),
            "verdict": self.verdict,
            "reason": self.reason,
            "score_formula": self.score_formula,
            "hypotheses": [item.as_dict() for item in self.hypotheses],
        }


def path_id(path: InvestigationPath) -> str:
    """Return a stable ID for an actual graph-derived candidate path."""
    payload = {
        "node_ids": path.node_ids,
        "relationships": path.relationships,
        "edge_ids": path.edge_ids,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "path-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


__all__ = [
    "CompetitionOutcome",
    "Hypothesis",
    "HypothesisCompetitionResult",
    "PathQuality",
    "TemporalValidity",
    "path_id",
]
