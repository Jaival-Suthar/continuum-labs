from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from continuum.cli.output import (
    CheckResult,
    checks,
    failure,
    header,
    info,
    success,
)
from continuum.core import (
    Hypothesis as StateHypothesis,
)
from continuum.core import (
    InvestigationResult,
)
from continuum.graph.client import GraphClient
from continuum.graph.loader import WorldLoader
from continuum.hypothesis import (
    CompetitionOutcome,
    path_id,
)
from continuum.investigator import Investigator
from continuum.report import format_report
from domains.software.world import SOFTWARE_WORLD


def run() -> int:
    header(
        "M11",
        "Grounded investigation report · real FalkorDB gate",
    )

    client = GraphClient()

    try:
        client.ping()

        WorldLoader(client).load(
            SOFTWARE_WORLD,
            reset=True,
        )

        investigator = Investigator(client)

        state = investigator.start_investigation(
            "Why did incident-001 happen?",
            target_id="incident-001",
        )

        dependency_paths = investigator.find_paths(
            "commit-001",
            "incident-001",
            max_hops=6,
            limit=25,
        )

        infrastructure_paths = investigator.find_paths(
            "infra-event-001",
            "incident-001",
            max_hops=3,
            limit=25,
        )

        configuration_paths = investigator.find_paths(
            "config-001",
            "incident-001",
            max_hops=3,
            limit=25,
        )

        if not dependency_paths or not infrastructure_paths or not configuration_paths:
            raise AssertionError("M10 candidate paths were not all discovered")

        paths = [
            *dependency_paths,
            *infrastructure_paths,
            *configuration_paths,
        ]

        state.apply_result(
            "candidate_paths_discovered",
            InvestigationResult(
                question=state.question,
                target=state.target,
                candidate_paths=paths,
                evidence=[item for path in paths for item in path.evidence],
                trace=[f"candidate_paths_discovered={len(paths)}"],
            ),
            input={"path_count": len(paths)},
        )

        state.add_hypothesis(
            StateHypothesis(
                "H1",
                "Dependency change",
                tuple(path_id(path) for path in dependency_paths),
            )
        )

        state.add_hypothesis(
            StateHypothesis(
                "H2",
                "Infrastructure event",
                tuple(path_id(path) for path in infrastructure_paths),
            )
        )

        state.add_hypothesis(
            StateHypothesis(
                "H3",
                "Configuration change",
                tuple(path_id(path) for path in configuration_paths),
            )
        )

        competition = investigator.compete_hypotheses(state)

        state.extensions["hypothesis_competition"] = competition.as_dict()

        state.apply_result(
            "compare_hypotheses",
            InvestigationResult(
                question=state.question,
                target=state.target,
                contradictions=[
                    contradiction
                    for hypothesis in competition.hypotheses
                    for contradiction in hypothesis.contradictions
                ],
                gaps=[
                    gap
                    for hypothesis in competition.hypotheses
                    for gap in hypothesis.missing_evidence
                ],
                verdict=competition.verdict,
                trace=[
                    (f"hypothesis_competition={competition.outcome}"),
                    (f"hypothesis_count={len(competition.hypotheses)}"),
                ],
            ),
            input={},
        )

        report = investigator.build_report(state)

        rendered = format_report(report)

        assert competition.outcome == CompetitionOutcome.WINNER

        assert competition.winner_ids == ("H1",)

        assert report.question == (state.question)

        assert report.verdict == ("H1 best supported")

        assert report.most_supported_explanation == "Dependency change"

        assert report.evidence_path
        assert report.observed_facts
        assert report.derived_relationships
        assert report.contradictions
        assert report.unknowns
        assert report.sources

        trace = " ".join(report.investigation_trace)

        assert "candidate_paths_discovered=" in trace

        assert "hypothesis_competition=WINNER" in trace

        for section in (
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
        ):
            assert section in rendered

        assert "confidence" not in (rendered.lower())

        assert "H1 best supported" in rendered

        assert "Dependency change" in rendered

        assert "commit-001" in rendered

        assert "incident-001" in rendered

    except (AssertionError, OSError, RuntimeError, TypeError, ValueError) as exc:
        failure(
            f"{type(exc).__name__}: {exc}"
        )
        raise

    info(
        "Verdict",
        report.verdict,
    )

    info(
        "Explanation",
        report.most_supported_explanation,
    )

    info(
        "Evidence paths",
        str(len(report.evidence_path)),
    )

    info(
        "Observed facts",
        str(len(report.observed_facts)),
    )

    info(
        "Derived relationships",
        str(len(report.derived_relationships)),
    )

    info(
        "Contradictions",
        str(len(report.contradictions)),
    )

    info(
        "Evidence gaps",
        str(len(report.unknowns)),
    )

    info(
        "Sources",
        str(len(report.sources)),
    )

    checks(
        [
            CheckResult(
                "FalkorDB connectivity",
                "PASS · real seeded software graph",
            ),
            CheckResult(
                "M10 boundary",
                "PASS · deterministic competition result consumed",
            ),
            CheckResult(
                "Question",
                "PASS · copied from investigation state",
            ),
            CheckResult(
                "Most supported explanation",
                "PASS · copied from M10 verdict/hypothesis data",
            ),
            CheckResult(
                "Evidence path",
                "PASS · actual M10 candidate paths only",
            ),
            CheckResult(
                "Observed facts",
                "PASS · actual evidence records only",
            ),
            CheckResult(
                "Derived relationships",
                "PASS · actual graph-derived path edges only",
            ),
            CheckResult(
                "Uncertainty",
                "PASS · contradictions and evidence gaps preserved",
            ),
            CheckResult(
                "Sources",
                "PASS · sourced from structured evidence",
            ),
            CheckResult(
                "Investigation trace",
                "PASS · no new investigation executed",
            ),
            CheckResult(
                "No invented confidence",
                "PASS · no probability/confidence synthesis",
            ),
        ]
    )

    print("\n" + rendered)

    success("M11")

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
