from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ReportStatement:
    """One report statement with explicit references into investigation state."""

    text: str
    classification: str
    evidence_ids: tuple[str, ...] = ()
    path_ids: tuple[str, ...] = ()
    hypothesis_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("ReportStatement.text must not be empty")
        if not self.classification.strip():
            raise ValueError("ReportStatement.classification must not be empty")


@dataclass(frozen=True)
class ReportPath:
    """A graph-derived evidence path rendered without changing its semantics."""

    path_id: str
    node_ids: tuple[str, ...]
    relationships: tuple[str, ...]
    temporal_status: str
    temporal_reason: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.path_id:
            raise ValueError("ReportPath.path_id must not be empty")

        if len(self.node_ids) != len(self.relationships) + 1:
            raise ValueError("ReportPath node/relationship lengths are inconsistent")


@dataclass(frozen=True)
class ReportSource:
    """Source material actually present in the structured investigation state."""

    id: str
    name: str
    status: str
    observed_at: datetime | str | None = None
    record: str | None = None
    span: str | None = None


@dataclass(frozen=True)
class InvestigationReport:
    """Deterministic M11 presentation model.

    This object contains only material already present in an M6-M10 result/state.
    It performs no graph queries, validation, scoring, temporal reasoning, or
    LLM synthesis.
    """

    question: str
    verdict: str
    most_supported_explanation: str
    evidence_path: tuple[ReportPath, ...] = ()
    observed_facts: tuple[ReportStatement, ...] = ()
    derived_relationships: tuple[ReportStatement, ...] = ()
    supported_inferences: tuple[ReportStatement, ...] = ()
    contradictions: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    sources: tuple[ReportSource, ...] = ()
    investigation_trace: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("InvestigationReport.question must not be empty")

        if not self.verdict.strip():
            raise ValueError("InvestigationReport.verdict must not be empty")

        if not self.most_supported_explanation.strip():
            raise ValueError(
                "InvestigationReport.most_supported_explanation must not be empty"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "verdict": self.verdict,
            "most_supported_explanation": self.most_supported_explanation,
            "evidence_path": [
                {
                    "path_id": item.path_id,
                    "node_ids": list(item.node_ids),
                    "relationships": list(item.relationships),
                    "temporal_status": item.temporal_status,
                    "temporal_reason": item.temporal_reason,
                    "evidence_ids": list(item.evidence_ids),
                }
                for item in self.evidence_path
            ],
            "observed_facts": [_statement_dict(item) for item in self.observed_facts],
            "derived_relationships": [
                _statement_dict(item) for item in self.derived_relationships
            ],
            "supported_inferences": [
                _statement_dict(item) for item in self.supported_inferences
            ],
            "contradictions": list(self.contradictions),
            "unknowns": list(self.unknowns),
            "sources": [
                {
                    "id": item.id,
                    "name": item.name,
                    "status": item.status,
                    "observed_at": (
                        item.observed_at.isoformat()
                        if isinstance(item.observed_at, datetime)
                        else item.observed_at
                    ),
                    "record": item.record,
                    "span": item.span,
                }
                for item in self.sources
            ],
            "investigation_trace": list(self.investigation_trace),
        }


def _statement_dict(item: ReportStatement) -> dict[str, Any]:
    return {
        "text": item.text,
        "classification": item.classification,
        "evidence_ids": list(item.evidence_ids),
        "path_ids": list(item.path_ids),
        "hypothesis_ids": list(item.hypothesis_ids),
    }
