from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TemporalConstraint:
    """A deterministic temporal rule attached to one controlled case."""

    subject_id: str
    object_id: str
    relation: str = "before"

    def __post_init__(self) -> None:
        if not self.subject_id or not self.object_id:
            raise ValueError("TemporalConstraint endpoints must not be empty")
        if self.relation not in {"before", "after"}:
            raise ValueError("TemporalConstraint.relation must be before or after")


@dataclass(frozen=True)
class EvaluationCase:
    """One independently specified controlled evaluation case.

    Ground truth is declared by the benchmark author, never inferred from a
    Continuum run. The case's World is intentionally kept outside this model
    so the persisted case file contains only evaluation truth and constraints.
    """

    case_id: str
    domain: str
    question: str
    ground_truth_path: tuple[str, ...]
    ground_truth_edge_ids: tuple[str, ...]
    distractor_paths: tuple[tuple[str, ...], ...]
    source_evidence: tuple[str, ...]
    temporal_constraints: tuple[TemporalConstraint, ...]
    expected_answer: str
    expected_edge_evidence: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must not be empty")
        if self.domain not in {"software", "supply-chain"}:
            raise ValueError("domain must be software or supply-chain")
        if not self.question.strip():
            raise ValueError("question must not be empty")
        if len(self.ground_truth_path) < 2:
            raise ValueError("ground_truth_path must contain at least two nodes")
        if len(self.ground_truth_edge_ids) != len(self.ground_truth_path) - 1:
            raise ValueError("ground_truth_edge_ids must match path hops")
        if not self.expected_answer.strip():
            raise ValueError("expected_answer must not be empty")
        if len(set(self.ground_truth_path)) != len(self.ground_truth_path):
            raise ValueError("ground_truth_path must not repeat nodes")
        if len(set(self.ground_truth_edge_ids)) != len(self.ground_truth_edge_ids):
            raise ValueError("ground_truth_edge_ids must be unique")
        unknown_edge_keys = set(self.expected_edge_evidence) - set(
            self.ground_truth_edge_ids
        )
        if unknown_edge_keys:
            raise ValueError(
                "expected_edge_evidence contains non-ground-truth edge ids: "
                + ", ".join(sorted(unknown_edge_keys))
            )

    @property
    def ground_truth_hops(self) -> int:
        return len(self.ground_truth_edge_ids)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ground_truth_path"] = list(self.ground_truth_path)
        payload["ground_truth_edge_ids"] = list(self.ground_truth_edge_ids)
        payload["distractor_paths"] = [list(path) for path in self.distractor_paths]
        payload["source_evidence"] = list(self.source_evidence)
        payload["temporal_constraints"] = [
            asdict(item) for item in self.temporal_constraints
        ]
        payload["expected_edge_evidence"] = {
            key: list(value) for key, value in self.expected_edge_evidence.items()
        }
        return payload

    def write_json(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
        return destination


@dataclass(frozen=True)
class PathRecoveryMetrics:
    exact_match: bool
    node_precision: float
    node_recall: float
    edge_precision: float
    edge_recall: float
    best_recovered_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceMetrics:
    claims_evaluated: int
    supported_claims: int
    unsupported_claims: int
    coverage: float
    unsupported_claim_rate: float


@dataclass(frozen=True)
class TemporalMetrics:
    constraints_evaluated: int
    constraints_satisfied: int
    path_valid: bool | None
    consistent: bool


@dataclass(frozen=True)
class EfficiencyMetrics:
    graph_operations: int
    graph_reads: int
    graph_writes: int
    investigation_steps: int
    nodes_explored: int
    edges_explored: int
    elapsed_ms: float


@dataclass(frozen=True)
class BaselineCaseResult:
    retrieved_ids: tuple[str, ...]
    retrieved_source_ids: tuple[str, ...]
    retrieved_edge_ids: tuple[str, ...]
    recovered_edges: tuple[tuple[str, str, str, str], ...]
    answer: str | None
    model: str | None
    path_recovery: PathRecoveryMetrics
    evidence: EvidenceMetrics
    temporal: TemporalMetrics


@dataclass(frozen=True)
class ContinuumCaseResult:
    target: str | None
    candidate_paths: tuple[tuple[str, ...], ...]
    evidence_ids: tuple[str, ...]
    path_recovery: PathRecoveryMetrics
    evidence: EvidenceMetrics
    temporal: TemporalMetrics
    efficiency: EfficiencyMetrics
    trace: tuple[str, ...]


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    domain: str
    question: str
    ground_truth_path: tuple[str, ...]
    ground_truth_edge_ids: tuple[str, ...]
    baseline: BaselineCaseResult
    continuum: ContinuumCaseResult
    temporal_constraints: tuple[TemporalConstraint, ...]
    expected_answer: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
        return destination
