from __future__ import annotations

from datetime import UTC, datetime

import pytest

from continuum.core import (
    Evidence,
    InvestigationPath,
    InvestigationResult,
    InvestigationState,
)
from continuum.core import Hypothesis as StateHypothesis
from continuum.hypothesis import (
    CompetitionOutcome,
    path_id,
)
from continuum.report import (
    GroundedReportBuilder,
    format_report,
)

UTC = datetime(
    2026,
    8,
    1,
    9,
    0,
    tzinfo=UTC,
)


def make_path(
    name: str,
    *,
    valid: bool = True,
    evidence: bool = True,
) -> InvestigationPath:
    item = (
        Evidence(
            f"e-{name}",
            f"s-{name}",
            "OBSERVED",
            UTC,
            f"record-{name}",
            "span-1",
        )
        if evidence
        else None
    )

    return InvestigationPath(
        node_ids=(
            f"{name}-a",
            f"{name}-b",
            f"{name}-c",
        ),
        relationships=(
            "DEPENDS_ON",
            "AFFECTS",
        ),
        edge_ids=(
            f"edge-{name}-1",
            f"edge-{name}-2",
        ),
        temporal_status=("VALID" if valid else "INVALID"),
        temporal_reason=("timestamps ordered" if valid else "effect precedes cause"),
        evidence=(item,) if item else (),
        supporting_relationship_count=(2 if evidence else 0),
        conflicting_relationship_count=(0 if valid else 1),
        missing_evidence_count=(0 if evidence else 2),
        node_records=(
            {},
            {},
            {},
        ),
        edge_records=(
            {},
            {},
        ),
    )


def state_with_competition(
    outcome: str,
    winner_ids: tuple[str, ...],
    hypotheses: list[dict],
    paths,
) -> InvestigationState:
    state = InvestigationState(
        "Why did incident-001 happen?",
        target="incident-001",
    )

    for item in hypotheses:
        state.add_hypothesis(
            StateHypothesis(
                item["id"],
                item["claim"],
                tuple(item["candidate_paths"]),
            )
        )

    state.candidate_paths.extend(paths)

    state.evidence.extend(item for path in paths for item in path.evidence)

    state.extensions["hypothesis_competition"] = {
        "outcome": outcome,
        "winner_ids": list(winner_ids),
        "verdict": (
            f"{winner_ids[0]} best supported"
            if outcome == CompetitionOutcome.WINNER
            else (
                f"{', '.join(winner_ids)} remain plausible"
                if outcome == CompetitionOutcome.AMBIGUOUS
                else "Insufficient evidence"
            )
        ),
        "hypotheses": hypotheses,
    }

    return state


def test_winner_report_uses_m10_winner_and_only_state_material():
    path = make_path("dependency")

    state = state_with_competition(
        CompetitionOutcome.WINNER,
        ("H1",),
        [
            {
                "id": "H1",
                "claim": "Dependency change",
                "candidate_paths": [path_id(path)],
                "contradictions": [],
                "missing_evidence": [],
            }
        ],
        [path],
    )

    report = GroundedReportBuilder().from_state(state)

    assert report.question == ("Why did incident-001 happen?")

    assert report.verdict == ("H1 best supported")

    assert report.most_supported_explanation == ("Dependency change")

    assert len(report.evidence_path) == 1

    assert report.evidence_path[0].path_id == path_id(path)

    assert report.observed_facts[0].evidence_ids == ("e-dependency",)

    assert all("confidence" not in item.text.lower() for item in report.observed_facts)


def test_ambiguous_report_never_collapses_multiple_plausible_hypotheses():
    h1 = make_path("h1")
    h2 = make_path("h2")

    state = state_with_competition(
        CompetitionOutcome.AMBIGUOUS,
        ("H1", "H2"),
        [
            {
                "id": "H1",
                "claim": "Dependency change",
                "candidate_paths": [path_id(h1)],
                "contradictions": [],
                "missing_evidence": [],
            },
            {
                "id": "H2",
                "claim": "Configuration change",
                "candidate_paths": [path_id(h2)],
                "contradictions": [],
                "missing_evidence": [],
            },
        ],
        [h1, h2],
    )

    report = GroundedReportBuilder().from_state(state)

    assert report.verdict == ("H1, H2 remain plausible")

    assert (
        "Multiple explanations remain plausible." in report.most_supported_explanation
    )

    assert "H1 — Dependency change" in report.most_supported_explanation

    assert "H2 — Configuration change" in report.most_supported_explanation

    assert "does not justify selecting one" in report.most_supported_explanation


def test_insufficient_report_says_insufficient_evidence_and_preserves_paths():
    path = make_path(
        "unknown",
        evidence=False,
    )

    state = state_with_competition(
        CompetitionOutcome.INSUFFICIENT,
        (),
        [
            {
                "id": "H1",
                "claim": "Unknown change",
                "candidate_paths": [path_id(path)],
                "contradictions": [],
                "missing_evidence": ["support missing"],
            }
        ],
        [path],
    )

    report = GroundedReportBuilder().from_state(state)

    assert report.verdict == ("Insufficient evidence")

    assert report.most_supported_explanation == ("Insufficient evidence.")

    assert report.unknowns == ("support missing",)

    assert len(report.evidence_path) == 1


def test_result_boundary_does_not_investigate_or_invent_verdict():
    path = make_path("result")

    result = InvestigationResult(
        question="Why did incident-001 happen?",
        target="incident-001",
        candidate_paths=[path],
        evidence=list(path.evidence),
        trace=["candidate_paths=1"],
    )

    report = GroundedReportBuilder().from_result(result)

    assert report.verdict == ("Insufficient evidence")

    assert report.most_supported_explanation == (
        "A graph-derived path was found, but no M10 "
        "verdict is present; the available result does "
        "not justify selecting a winning explanation."
    )

    assert report.investigation_trace == ("candidate_paths=1",)


def test_missing_m10_boundary_is_rejected_for_state():
    state = InvestigationState("Why did incident-001 happen?")

    with pytest.raises(
        ValueError,
        match="hypothesis_competition",
    ):
        GroundedReportBuilder().from_state(state)


def test_formatter_contains_exact_required_sections_and_trace_references():
    path = make_path("format")

    result = InvestigationResult(
        question="Why did incident-001 happen?",
        target="incident-001",
        candidate_paths=[path],
        evidence=list(path.evidence),
        contradictions=["A contradiction"],
        gaps=["A missing source"],
        trace=[
            "outcome_located=incident-001",
            "candidate_paths=1",
        ],
        verdict="H1 best supported",
    )

    text = format_report(GroundedReportBuilder().from_result(result))

    required = (
        "QUESTION",
        "MOST SUPPORTED EXPLANATION",
        "EVIDENCE PATH",
        "OBSERVED FACTS",
        "DERIVED RELATIONSHIPS",
        "SUPPORTED INFERENCES",
        "CONTRADICTIONS",
        "UNKNOWN / EVIDENCE GAPS",
        "SOURCES",
        "INVESTIGATION TRACE",
    )

    positions = [text.index(section) for section in required]

    assert positions == sorted(positions)

    assert "outcome_located=incident-001" in text

    assert path_id(path) in text

    assert "s-format" in text
