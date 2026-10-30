from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from continuum.core import World
from continuum.validation import Claim


class FailureType:
    MISSING_EVIDENCE: ClassVar[str] = "missing_evidence"
    MULTIPLE_PLAUSIBLE_PATHS: ClassVar[str] = "multiple_plausible_paths"
    TEMPORAL_CONTRADICTION: ClassVar[str] = "temporal_contradiction"
    MISLEADING_DOCUMENT: ClassVar[str] = "misleading_document"
    ALL: ClassVar[frozenset[str]] = frozenset(
        {
            MISSING_EVIDENCE,
            MULTIPLE_PLAUSIBLE_PATHS,
            TEMPORAL_CONTRADICTION,
            MISLEADING_DOCUMENT,
        }
    )


@dataclass(frozen=True)
class FailureCase:
    """Independently authored M14 failure fixture.

    The world and probe are the test input. Expected states are authored here,
    never derived from a Continuum execution.
    """

    case_id: str
    domain: str
    failure_type: str
    world: World
    question: str
    expected_behavior: str
    expected_evidence_state: str
    expected_path_state: str
    expected_hypothesis_state: str
    probe_claim: Claim | None = None
    retrieval_query: str | None = None
    expected_retrieved_document_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("FailureCase.case_id must not be empty")
        if self.domain.strip() == "":
            raise ValueError("FailureCase.domain must not be empty")
        if self.failure_type not in FailureType.ALL:
            raise ValueError(f"Unsupported M14 failure type: {self.failure_type}")
        if not self.question.strip():
            raise ValueError("FailureCase.question must not be empty")
        if not self.expected_behavior.strip():
            raise ValueError("FailureCase.expected_behavior must not be empty")
        if not self.expected_evidence_state.strip():
            raise ValueError("FailureCase.expected_evidence_state must not be empty")
        if not self.expected_path_state.strip():
            raise ValueError("FailureCase.expected_path_state must not be empty")
        if not self.expected_hypothesis_state.strip():
            raise ValueError("FailureCase.expected_hypothesis_state must not be empty")
        if (
            self.expected_retrieved_document_id is not None
            and self.retrieval_query is None
        ):
            raise ValueError("expected_retrieved_document_id requires retrieval_query")
        self.world.validate()

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "case_id": self.case_id,
            "domain": self.domain,
            "failure_type": self.failure_type,
            "question": self.question,
            "expected_behavior": self.expected_behavior,
            "expected_evidence_state": self.expected_evidence_state,
            "expected_path_state": self.expected_path_state,
            "expected_hypothesis_state": self.expected_hypothesis_state,
            "probe_claim": (
                {
                    "subject": self.probe_claim.subject,
                    "relationship": self.probe_claim.relationship,
                    "object": self.probe_claim.object,
                }
                if self.probe_claim
                else None
            ),
            "retrieval_query": self.retrieval_query,
            "expected_retrieved_document_id": self.expected_retrieved_document_id,
            "metadata": self.metadata,
            "world": {
                "name": self.world.name,
                "ontology": self.world.ontology.name,
                "nodes": [
                    {
                        "id": node.id,
                        "label": node.label,
                        "name": node.name,
                        "timestamp": (
                            node.timestamp.isoformat() if node.timestamp else None
                        ),
                        "properties": node.properties,
                    }
                    for node in self.world.data.nodes()
                ],
                "edges": [
                    {
                        "edge_id": edge.stable_id,
                        "source_id": edge.source_id,
                        "relationship": edge.relationship,
                        "target_id": edge.target_id,
                        "timestamp": (
                            edge.timestamp.isoformat() if edge.timestamp else None
                        ),
                        "evidence_source_ids": list(edge.evidence_source_ids),
                        "evidence_status": edge.evidence_status,
                        "properties": edge.properties,
                    }
                    for edge in self.world.data.edges()
                ],
            },
        }
        return payload

    def write_json(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return destination


@dataclass(frozen=True)
class FailureCaseResult:
    case_id: str
    domain: str
    failure_type: str
    expected_behavior: str
    actual_behavior: str
    expected_evidence_state: str
    actual_evidence_state: str
    expected_path_state: str
    actual_path_state: str
    expected_hypothesis_state: str
    actual_hypothesis_state: str
    validation_passed: bool
    target: str | None
    candidate_paths: tuple[tuple[str, ...], ...]
    valid_paths: tuple[tuple[str, ...], ...]
    invalid_paths: tuple[tuple[str, ...], ...]
    evidence_ids: tuple[str, ...]
    contradictions: tuple[str, ...]
    gaps: tuple[str, ...]
    temporal_checks: tuple[str, ...]
    hypotheses: tuple[dict[str, Any], ...]
    competition_outcome: str = ""
    competition_verdict: str = ""
    retrieved_document_ids: tuple[str, ...] = ()
    probe_classification: str | None = None
    probe_message: str | None = None
    trace: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return destination
