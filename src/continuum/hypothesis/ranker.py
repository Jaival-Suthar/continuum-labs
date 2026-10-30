from __future__ import annotations

from collections.abc import Iterable

from continuum.hypothesis.model import (
    CompetitionOutcome,
    Hypothesis,
    HypothesisCompetitionResult,
    PathQuality,
)

PATH_QUALITY_POINTS = {
    PathQuality.STRONG: 2,
    PathQuality.MODERATE: 1,
    PathQuality.WEAK: 0,
}


def score_hypothesis(hypothesis: Hypothesis) -> int:
    """Apply the documented M10 ordinal scoring rule; never a probability."""
    support = hypothesis.support_count
    temporal = hypothesis.valid_path_count - hypothesis.invalid_path_count
    path_quality = PATH_QUALITY_POINTS[hypothesis.path_quality]
    contradiction = hypothesis.contradiction_count
    missing_evidence = hypothesis.missing_evidence_count
    return support + temporal + path_quality - contradiction - missing_evidence


def rank_hypotheses(
    hypotheses: Iterable[Hypothesis],
) -> HypothesisCompetitionResult:
    """Rank competing hypotheses and preserve ambiguity/uncertainty."""
    items = [
        Hypothesis(
            id=item.id,
            claim=item.claim,
            supporting_evidence=item.supporting_evidence,
            contradictions=item.contradictions,
            missing_evidence=item.missing_evidence,
            temporal_validity=item.temporal_validity,
            candidate_paths=item.candidate_paths,
            path_quality=item.path_quality,
            score=score_hypothesis(item),
            claim_validations=item.claim_validations,
        )
        for item in hypotheses
    ]

    if not items:
        return HypothesisCompetitionResult(
            CompetitionOutcome.INSUFFICIENT,
            (),
            reason="No hypotheses were supplied.",
        )

    plausible = [item for item in items if item.plausible]
    if not plausible:
        return HypothesisCompetitionResult(
            CompetitionOutcome.INSUFFICIENT,
            tuple(sorted(items, key=lambda item: item.id)),
            reason="No hypothesis has both positive graph/evidence support and a valid candidate path without contradiction.",
        )

    ordered = sorted(
        items,
        key=lambda item: (item.plausible, item.score, item.id),
        reverse=True,
    )
    top_score = max(item.score for item in plausible)
    leaders = sorted(
        (item for item in plausible if item.score == top_score),
        key=lambda item: item.id,
    )

    if len(leaders) > 1:
        return HypothesisCompetitionResult(
            CompetitionOutcome.AMBIGUOUS,
            tuple(ordered),
            winner_ids=tuple(item.id for item in leaders),
            reason="Multiple plausible hypotheses have the same highest deterministic score.",
        )

    return HypothesisCompetitionResult(
        CompetitionOutcome.WINNER,
        tuple(ordered),
        winner_ids=(leaders[0].id,),
        reason="One plausible hypothesis has the highest deterministic score.",
    )
