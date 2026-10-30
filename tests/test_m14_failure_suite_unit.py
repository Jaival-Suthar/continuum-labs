from __future__ import annotations

from datetime import UTC, datetime

from continuum.core import Evidence, InvestigationPath
from continuum.failure import FailureType, all_failure_cases
from continuum.failure.runner import (
    _evidence_state,
    _hypothesis_state,
    _maximal_paths,
    _path_state,
)
from continuum.hypothesis import (
    CompetitionOutcome,
    Hypothesis,
    PathQuality,
    TemporalValidity,
)


def _path(
    name: str,
    *,
    valid: bool | None,
    evidence: int,
    missing: int = 0,
) -> InvestigationPath:
    timestamp = datetime(2026, 9, 1, 10, tzinfo=UTC)
    evidence_items = tuple(
        Evidence(f"{name}-e-{index}", f"{name}-s-{index}", "OBSERVED")
        for index in range(evidence)
    )
    return InvestigationPath(
        node_ids=(f"{name}-cause", f"{name}-service", f"{name}-incident"),
        relationships=("AFFECTS", "RESULTED_IN"),
        edge_ids=(f"{name}-e1", f"{name}-e2"),
        temporal_status=(
            "VALID" if valid is True else "INVALID" if valid is False else "UNKNOWN"
        ),
        temporal_reason="test",
        evidence=evidence_items,
        supporting_relationship_count=2 if evidence else 0,
        conflicting_relationship_count=1 if valid is False else 0,
        missing_evidence_count=missing,
        node_records=(
            {"timestamp": timestamp},
            {"timestamp": timestamp},
            {"timestamp": timestamp},
        ),
        edge_records=(
            {"timestamp": timestamp},
            {"timestamp": timestamp},
        ),
    )


def test_m14_defines_exactly_four_independent_failure_families():
    cases = all_failure_cases()
    assert {case.failure_type for case in cases} == set(FailureType.ALL)
    assert len(cases) == 4
    assert len({case.case_id for case in cases}) == 4


def test_m14_expected_behavior_is_fixture_authored():
    cases = {case.failure_type: case for case in all_failure_cases()}
    assert (
        cases[FailureType.MISSING_EVIDENCE].expected_behavior
        == "Insufficient evidence."
    )
    assert (
        cases[FailureType.MULTIPLE_PLAUSIBLE_PATHS].expected_behavior
        == "Multiple explanations remain plausible."
    )
    assert (
        cases[FailureType.TEMPORAL_CONTRADICTION].expected_behavior == "Path rejected."
    )
    assert (
        cases[FailureType.MISLEADING_DOCUMENT].expected_behavior
        == "Unsupported relationship rejected."
    )


def test_missing_evidence_is_an_incomplete_evidence_state():
    path = _path("gap", valid=True, evidence=1, missing=1)
    assert _evidence_state((path,)) == "gap"
    assert _path_state((path,)) == "plausible_but_incomplete"


def test_two_maximal_valid_paths_are_preserved_for_competition():
    first = _path("h1", valid=True, evidence=2)
    second = _path("h2", valid=True, evidence=2)
    maximal = _maximal_paths((first, second))
    assert maximal == (first, second)


def test_temporal_contradiction_is_an_invalid_path():
    path = _path("bad-time", valid=False, evidence=2)
    assert _evidence_state((path,)) == "contradicted"
    assert _path_state((path,)) == "invalid"


def test_m10_plausibility_requires_complete_evidence():
    path = _path("incomplete", valid=True, evidence=1, missing=1)
    hypothesis = Hypothesis(
        id="H1",
        claim="Incomplete path",
        supporting_evidence=path.evidence,
        missing_evidence=("missing provenance",),
        temporal_validity=TemporalValidity.VALID,
        candidate_paths=(path,),
        path_quality=PathQuality.MODERATE,
    )
    assert not hypothesis.plausible


def test_failure_hypothesis_state_mapping():
    assert (
        _hypothesis_state(
            CompetitionOutcome.AMBIGUOUS, FailureType.MULTIPLE_PLAUSIBLE_PATHS
        )
        == "ambiguous"
    )
    assert (
        _hypothesis_state(CompetitionOutcome.INSUFFICIENT, FailureType.MISSING_EVIDENCE)
        == "insufficient"
    )
    assert (
        _hypothesis_state(
            CompetitionOutcome.INSUFFICIENT, FailureType.TEMPORAL_CONTRADICTION
        )
        == "rejected"
    )
    assert (
        _hypothesis_state(CompetitionOutcome.WINNER, FailureType.MISLEADING_DOCUMENT)
        == "unsupported"
    )


def test_misleading_fixture_retrieval_target_is_a_corpus_document():
    case = next(
        case
        for case in all_failure_cases()
        if case.failure_type == FailureType.MISLEADING_DOCUMENT
    )

    assert case.probe_claim is not None
    assert case.expected_retrieved_document_id == "node:m14-misleading-document"
    assert case.probe_claim.subject == "m14-misleading-deployment"
