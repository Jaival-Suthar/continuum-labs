from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from continuum.baseline import BaselineRunner, build_corpus
from continuum.core import Hypothesis as StateHypothesis
from continuum.core import InvestigationPath, InvestigationState
from continuum.failure.model import FailureCase, FailureCaseResult, FailureType
from continuum.graph.client import GraphClient
from continuum.graph.loader import WorldLoader
from continuum.hypothesis import CompetitionOutcome, path_id
from continuum.investigator import Investigator


@dataclass
class FailureSuiteRunner:
    """Execute M14 fixtures against the real graph investigation stack."""

    graph: GraphClient
    max_hops: int = 6
    path_limit: int = 25
    top_k: int = 8

    def __post_init__(self) -> None:
        if self.max_hops < 1:
            raise ValueError("max_hops must be >= 1")
        if self.path_limit < 1:
            raise ValueError("path_limit must be >= 1")
        if self.top_k < 1:
            raise ValueError("top_k must be >= 1")

    def run_case(self, case: FailureCase) -> FailureCaseResult:
        """Seed one isolated world and execute the actual investigator."""
        WorldLoader(self.graph).load(case.world, reset=True)

        retrieved_document_ids: tuple[str, ...] = ()
        if case.retrieval_query is not None:
            retrieved = BaselineRunner(build_corpus(case.world)).retrieve(
                case.retrieval_query,
                top_k=self.top_k,
            )
            retrieved_document_ids = tuple(item.document.id for item in retrieved)

        started = time.perf_counter()
        investigator = Investigator(self.graph, case.world)
        investigation = investigator.investigate(case.question)
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        candidates = _unique_paths(investigation.candidate_paths)
        valid_paths = tuple(
            path.node_ids for path in candidates if path.temporally_valid is True
        )
        invalid_paths = tuple(
            path.node_ids for path in candidates if path.temporally_valid is False
        )

        state = investigator.start_investigation(
            case.question,
            target_id=investigation.target,
        )
        state.candidate_paths.extend(candidates)
        _add_path_hypotheses(state, candidates)
        competition = investigator.compete_hypotheses(state)

        probe_classification = None
        probe_message = None

        if case.probe_claim is not None:
            validation = investigator.validate_claim(case.probe_claim)
            probe_classification = validation.classification
            probe_message = validation.message

        if case.failure_type == FailureType.MISLEADING_DOCUMENT:
            actual_evidence_state = (
                "unsupported"
                if probe_classification == "UNKNOWN"
                else "unexpected_support"
            )
            actual_path_state = (
                "no_graph_relationship"
                if probe_classification == "UNKNOWN"
                else "unexpected_graph_relationship"
            )
        else:
            actual_evidence_state = _evidence_state(candidates)
            actual_path_state = _path_state(candidates)

        actual_hypothesis_state = _hypothesis_state(
            competition.outcome,
            case.failure_type,
        )
        actual_behavior = _behavior(
            case.failure_type,
            actual_evidence_state,
            actual_path_state,
            actual_hypothesis_state,
            competition,
        )

        validation_passed = _validate_expected(
            case,
            actual_behavior=actual_behavior,
            actual_evidence_state=actual_evidence_state,
            actual_path_state=actual_path_state,
            actual_hypothesis_state=actual_hypothesis_state,
            retrieved_document_ids=retrieved_document_ids,
            probe_classification=probe_classification,
        )

        hypotheses = tuple(
            {
                **hypothesis.as_dict(),
                "candidate_paths": [
                    path_id(path) for path in hypothesis.candidate_paths
                ],
            }
            for hypothesis in competition.hypotheses
        )

        return FailureCaseResult(
            case_id=case.case_id,
            domain=case.domain,
            failure_type=case.failure_type,
            expected_behavior=case.expected_behavior,
            actual_behavior=actual_behavior,
            expected_evidence_state=case.expected_evidence_state,
            actual_evidence_state=actual_evidence_state,
            expected_path_state=case.expected_path_state,
            actual_path_state=actual_path_state,
            expected_hypothesis_state=case.expected_hypothesis_state,
            actual_hypothesis_state=actual_hypothesis_state,
            validation_passed=validation_passed,
            target=investigation.target,
            candidate_paths=tuple(path.node_ids for path in candidates),
            valid_paths=valid_paths,
            invalid_paths=invalid_paths,
            evidence_ids=tuple(item.id for item in investigation.evidence),
            contradictions=tuple(investigation.contradictions),
            gaps=tuple(investigation.gaps),
            temporal_checks=tuple(investigation.temporal_checks),
            hypotheses=hypotheses,
            competition_outcome=competition.outcome,
            competition_verdict=competition.verdict,
            retrieved_document_ids=retrieved_document_ids,
            probe_classification=probe_classification,
            probe_message=probe_message,
            trace=(*investigation.trace, f"elapsed_ms={elapsed_ms:.3f}"),
            metadata={
                "max_hops": self.max_hops,
                "path_limit": self.path_limit,
            },
        )

    def run_all(
        self,
        cases: tuple[FailureCase, ...],
    ) -> tuple[FailureCaseResult, ...]:
        if not cases:
            raise ValueError("at least one M14 failure case is required")
        return tuple(self.run_case(case) for case in cases)


def _unique_paths(
    paths: tuple[InvestigationPath, ...] | list[InvestigationPath],
) -> tuple[InvestigationPath, ...]:
    seen: set[tuple[str, ...]] = set()
    unique: list[InvestigationPath] = []

    for path in paths:
        if path.node_ids in seen:
            continue
        seen.add(path.node_ids)
        unique.append(path)

    return tuple(unique)


def _maximal_paths(
    paths: tuple[InvestigationPath, ...],
) -> tuple[InvestigationPath, ...]:
    """Keep source-to-target explanations, not their suffix subpaths."""
    node_sets = {path.node_ids for path in paths}
    selected: list[InvestigationPath] = []

    for path in paths:
        suffix_exists = any(
            other != path.node_ids
            and len(other) > len(path.node_ids)
            and len(other) >= len(path.node_ids)
            and tuple(other[-len(path.node_ids) :]) == path.node_ids
            for other in node_sets
        )

        if not suffix_exists:
            selected.append(path)

    return tuple(selected)


def _add_path_hypotheses(
    state: InvestigationState,
    paths: tuple[InvestigationPath, ...],
) -> None:
    for index, path in enumerate(_maximal_paths(paths), start=1):
        state.add_hypothesis(
            StateHypothesis(
                id=f"H{index}",
                description=(f"Candidate explanation via {' -> '.join(path.node_ids)}"),
                candidate_path_ids=(path_id(path),),
            )
        )


def _evidence_state(paths: tuple[InvestigationPath, ...]) -> str:
    if not paths:
        return "none"

    if any(path.temporally_valid is False for path in paths):
        return "contradicted"

    if any(path.missing_evidence_count for path in paths):
        return "gap"

    if any(path.evidence for path in paths):
        return "supported"

    return "unknown"


def _path_state(paths: tuple[InvestigationPath, ...]) -> str:
    if not paths:
        return "no_path"

    valid = [path for path in paths if path.temporally_valid is True]
    invalid = [path for path in paths if path.temporally_valid is False]

    if invalid and not valid:
        return "invalid"

    maximal = _maximal_paths(paths)
    maximal_valid = [path for path in maximal if path.temporally_valid is True]

    if len(maximal_valid) >= 2:
        return "multiple_valid"

    if any(path.missing_evidence_count for path in maximal):
        return "plausible_but_incomplete"

    return "valid"


def _hypothesis_state(outcome: str, failure_type: str) -> str:
    if failure_type == FailureType.TEMPORAL_CONTRADICTION:
        return "rejected"

    if failure_type == FailureType.MISLEADING_DOCUMENT:
        return "unsupported"

    if outcome == CompetitionOutcome.AMBIGUOUS:
        return "ambiguous"

    if outcome == CompetitionOutcome.INSUFFICIENT:
        return "insufficient"

    return "winner"


def _behavior(
    failure_type: str,
    evidence_state: str,
    path_state: str,
    hypothesis_state: str,
    competition: Any,
) -> str:
    if failure_type == FailureType.MISSING_EVIDENCE:
        return "Insufficient evidence."

    if failure_type == FailureType.MULTIPLE_PLAUSIBLE_PATHS:
        if competition.outcome == CompetitionOutcome.AMBIGUOUS:
            return "Multiple explanations remain plausible."
        return competition.verdict

    if failure_type == FailureType.TEMPORAL_CONTRADICTION:
        if path_state == "invalid":
            return "Path rejected."
        return competition.verdict

    if failure_type == FailureType.MISLEADING_DOCUMENT:
        return "Unsupported relationship rejected."

    raise ValueError(f"Unhandled M14 failure type: {failure_type}")


def _validate_expected(
    case: FailureCase,
    *,
    actual_behavior: str,
    actual_evidence_state: str,
    actual_path_state: str,
    actual_hypothesis_state: str,
    retrieved_document_ids: tuple[str, ...],
    probe_classification: str | None,
) -> bool:
    if actual_behavior != case.expected_behavior:
        return False

    if actual_evidence_state != case.expected_evidence_state:
        return False

    if actual_path_state != case.expected_path_state:
        return False

    if actual_hypothesis_state != case.expected_hypothesis_state:
        return False

    if (
        case.expected_retrieved_document_id is not None
        and case.expected_retrieved_document_id not in retrieved_document_ids
    ):
        return False

    return not (
        case.failure_type == FailureType.MISLEADING_DOCUMENT
        and probe_classification != "UNKNOWN"
    )


def aggregate_failure_results(
    results: tuple[FailureCaseResult, ...],
) -> dict[str, Any]:
    if not results:
        raise ValueError("cannot aggregate an empty M14 result set")

    passed = sum(result.validation_passed for result in results)

    by_type = {
        failure_type: {
            "cases": sum(result.failure_type == failure_type for result in results),
            "passed": sum(
                result.failure_type == failure_type and result.validation_passed
                for result in results
            ),
        }
        for failure_type in sorted({result.failure_type for result in results})
    }

    return {
        "suite": "M14 Failure Suite",
        "case_count": len(results),
        "passed_cases": passed,
        "failed_cases": len(results) - passed,
        "pass_rate": passed / len(results),
        "by_failure_type": by_type,
        "all_cases_passed": passed == len(results),
    }
