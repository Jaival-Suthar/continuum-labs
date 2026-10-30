from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from continuum.core import Evidence, InvestigationPath
from continuum.core import Hypothesis as StateHypothesis
from continuum.hypothesis import (
    CompetitionOutcome,
    Hypothesis,
    HypothesisEvaluator,
    PathQuality,
    TemporalValidity,
    path_id,
    rank_hypotheses,
    score_hypothesis,
)
from continuum.validation import Claim, ClaimClassification, ClaimValidation

UTC = datetime.fromisoformat("2026-08-01T00:00:00+00:00")


def make_path(name: str, valid: bool | None, evidence: bool) -> InvestigationPath:
    item = (
        Evidence(f"e-{name}", f"s-{name}", ClaimClassification.OBSERVED)
        if evidence
        else None
    )
    return InvestigationPath(
        node_ids=(f"{name}-a", f"{name}-b"),
        relationships=("AFFECTS",),
        edge_ids=(f"edge-{name}",),
        temporal_status="VALID"
        if valid is True
        else "INVALID"
        if valid is False
        else "UNKNOWN",
        temporal_reason="unit test",
        evidence=(item,) if item else (),
        supporting_relationship_count=1 if evidence else 0,
        conflicting_relationship_count=1 if valid is False else 0,
        missing_evidence_count=0 if evidence else 1,
        node_records=({"timestamp": UTC}, {"timestamp": UTC}),
        edge_records=({"timestamp": UTC},),
    )


@dataclass
class FakeInvestigator:
    classifications: dict[tuple[str, str, str], str]

    def validate_claim(self, claim: Claim) -> ClaimValidation:
        classification = self.classifications.get(
            claim.key, ClaimClassification.UNKNOWN
        )
        evidence = ()
        contradictions = ()
        if classification == ClaimClassification.OBSERVED:
            evidence = (
                Evidence(
                    f"e-{claim.subject}",
                    f"s-{claim.subject}",
                    ClaimClassification.OBSERVED,
                ),
            )
        if classification == ClaimClassification.CONTRADICTED:
            contradictions = (f"{claim.key} contradicted",)
        return ClaimValidation(
            claim=claim,
            classification=classification,
            evidence=evidence,
            contradictions=contradictions,
            graph_valid=classification != ClaimClassification.UNKNOWN,
            evidence_found=bool(evidence),
        )

    def find_conflicting_evidence(self, paths):
        return [
            f"Path {' -> '.join(path.node_ids)} rejected: {path.temporal_reason}"
            for path in paths
            if path.temporally_valid is False
        ]


def evaluated(id_: str, plausible: bool) -> Hypothesis:
    path = make_path(id_, True, plausible)
    claim = Claim(f"{id_}-a", "AFFECTS", f"{id_}-b")
    validation = ClaimValidation(
        claim=claim,
        classification=ClaimClassification.OBSERVED
        if plausible
        else ClaimClassification.UNKNOWN,
        evidence=(Evidence(f"e-{id_}", f"s-{id_}", ClaimClassification.OBSERVED),)
        if plausible
        else (),
        graph_valid=plausible,
        evidence_found=plausible,
    )
    return Hypothesis(
        id=id_,
        claim=id_,
        supporting_evidence=validation.evidence,
        contradictions=() if plausible else ("no support",),
        missing_evidence=() if plausible else ("missing",),
        temporal_validity=TemporalValidity.VALID
        if plausible
        else TemporalValidity.UNKNOWN,
        candidate_paths=(path,) if plausible else (),
        path_quality=PathQuality.STRONG if plausible else PathQuality.WEAK,
        claim_validations=(validation,),
    )


def test_path_id_is_stable_and_graph_derived():
    path = make_path("x", True, True)
    assert path_id(path) == path_id(path)
    assert path_id(path).startswith("path-")


def test_evaluator_uses_m9_and_m6_signals():
    path = make_path("h1", True, True)
    hypothesis = StateHypothesis(
        "H1", "Dependency change", candidate_path_ids=(path_id(path),)
    )
    evaluator = HypothesisEvaluator(
        FakeInvestigator({("h1-a", "AFFECTS", "h1-b"): ClaimClassification.OBSERVED})
    )
    result = evaluator.evaluate(hypothesis, {path_id(path): path})
    assert result.support_count == 1
    assert result.supporting_evidence[0].id == "e-h1-a"
    assert result.temporal_validity == TemporalValidity.VALID
    assert result.path_quality == PathQuality.STRONG
    assert result.plausible
    assert score_hypothesis(result) == 4


def test_evaluator_exposes_missing_evidence():
    path = make_path("h2", True, False)
    hypothesis = StateHypothesis(
        "H2", "Infrastructure event", candidate_path_ids=(path_id(path),)
    )
    result = HypothesisEvaluator(FakeInvestigator({})).evaluate(
        hypothesis, {path_id(path): path}
    )
    assert result.support_count == 0
    assert result.missing_evidence
    assert not result.plausible


def test_evaluator_rejects_temporal_contradiction():
    path = make_path("h3", False, True)
    hypothesis = StateHypothesis(
        "H3", "Configuration change", candidate_path_ids=(path_id(path),)
    )
    evaluator = HypothesisEvaluator(
        FakeInvestigator(
            {("h3-a", "AFFECTS", "h3-b"): ClaimClassification.CONTRADICTED}
        )
    )
    result = evaluator.evaluate(hypothesis, {path_id(path): path})
    assert result.temporal_validity == TemporalValidity.INVALID
    assert result.contradictions
    assert not result.plausible


def test_ranker_returns_winner():
    result = rank_hypotheses([evaluated("H2", False), evaluated("H1", True)])
    assert result.outcome == CompetitionOutcome.WINNER
    assert result.winner_ids == ("H1",)
    assert result.verdict == "H1 best supported"


def test_ranker_returns_ambiguity_for_equal_plausible_hypotheses():
    result = rank_hypotheses([evaluated("H1", True), evaluated("H2", True)])
    assert result.outcome == CompetitionOutcome.AMBIGUOUS
    assert result.winner_ids == ("H1", "H2")
    assert result.verdict == "H1, H2 remain plausible"


def test_ranker_returns_insufficient_evidence():
    result = rank_hypotheses([evaluated("H1", False), evaluated("H2", False)])
    assert result.outcome == CompetitionOutcome.INSUFFICIENT
    assert result.winner_ids == ()
    assert result.verdict == "Insufficient evidence"


def test_score_is_not_a_probability():
    assert score_hypothesis(evaluated("H1", True)) == 4


def test_m8_compare_hypotheses_tool_crosses_m10_boundary():
    from continuum.agent.tools import CompareHypothesesTool
    from continuum.core import InvestigationState

    class Competition:
        outcome = CompetitionOutcome.WINNER
        verdict = "H1 best supported"
        hypotheses = ()

        def as_dict(self):
            return {"outcome": self.outcome, "verdict": self.verdict}

    class Investigator:
        def compete_hypotheses(self, state):
            assert state.hypotheses
            return Competition()

    state = InvestigationState("Why did incident-001 happen?")
    state.add_hypothesis(StateHypothesis("H1", "Dependency change"))
    updated = CompareHypothesesTool().execute(Investigator(), state, {})
    assert updated is state
    assert state.extensions["hypothesis_competition"]["verdict"] == "H1 best supported"
    assert state.history[-1].operation == "compare_hypotheses"
