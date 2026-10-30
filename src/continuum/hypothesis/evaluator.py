from __future__ import annotations

from collections.abc import Iterable

from continuum.core import Hypothesis as StateHypothesis
from continuum.core import InvestigationPath, InvestigationState
from continuum.hypothesis.model import (
    Hypothesis,
    HypothesisCompetitionResult,
    PathQuality,
    TemporalValidity,
)
from continuum.hypothesis.ranker import rank_hypotheses
from continuum.validation import Claim, ClaimClassification, ClaimValidation


class HypothesisEvaluator:
    """Deterministically evaluate M7 hypotheses with M6 paths and M9 validation."""

    def __init__(self, investigator) -> None:
        self.investigator = investigator

    def evaluate_state(
        self,
        state: InvestigationState,
    ) -> HypothesisCompetitionResult:
        if not isinstance(state, InvestigationState):
            raise TypeError("state must be an InvestigationState")

        paths_by_id = {self._path_id(path): path for path in state.candidate_paths}
        evaluated = [
            self.evaluate(hypothesis, paths_by_id) for hypothesis in state.hypotheses
        ]
        return rank_hypotheses(evaluated)

    def evaluate(
        self,
        hypothesis: StateHypothesis,
        paths_by_id: dict[str, InvestigationPath],
    ) -> Hypothesis:
        if not isinstance(hypothesis, StateHypothesis):
            raise TypeError("hypothesis must be an M7 core Hypothesis")

        paths = tuple(
            paths_by_id[path_ref]
            for path_ref in hypothesis.candidate_path_ids
            if path_ref in paths_by_id
        )
        missing_path_refs = [
            path_ref
            for path_ref in hypothesis.candidate_path_ids
            if path_ref not in paths_by_id
        ]

        validations = self._validate_path_claims(paths)
        supporting_evidence = self._unique_evidence(
            evidence for validation in validations for evidence in validation.evidence
        )

        contradictions = self._unique_strings(
            contradiction
            for validation in validations
            for contradiction in validation.contradictions
        )
        contradictions = self._unique_strings(
            (*contradictions, *self.investigator.find_conflicting_evidence(paths))
        )

        missing = self._missing_evidence(validations, paths)
        missing = tuple(
            dict.fromkeys(
                (
                    *missing,
                    *(
                        f"Candidate path {path_ref} is not present in investigation state"
                        for path_ref in missing_path_refs
                    ),
                )
            )
        )
        temporal = self._temporal_validity(validations, paths)
        quality = self._path_quality(paths)

        return Hypothesis(
            id=hypothesis.id,
            claim=hypothesis.description,
            supporting_evidence=supporting_evidence,
            contradictions=contradictions,
            missing_evidence=missing,
            temporal_validity=temporal,
            candidate_paths=paths,
            path_quality=quality,
            claim_validations=validations,
        )

    def _validate_path_claims(
        self,
        paths: Iterable[InvestigationPath],
    ) -> tuple[ClaimValidation, ...]:
        seen: set[tuple[str, str, str]] = set()
        validations: list[ClaimValidation] = []
        for path in paths:
            for subject, relationship, target in zip(
                path.node_ids[:-1],
                path.relationships,
                path.node_ids[1:],
                strict=True,
            ):
                claim = Claim(subject, relationship, target)
                if claim.key in seen:
                    continue
                seen.add(claim.key)
                validations.append(self.investigator.validate_claim(claim))
        return tuple(validations)

    @staticmethod
    def _missing_evidence(
        validations: Iterable[ClaimValidation],
        paths: Iterable[InvestigationPath],
    ) -> tuple[str, ...]:
        missing: list[str] = []
        for validation in validations:
            if validation.classification == ClaimClassification.UNKNOWN:
                missing.append(
                    f"{validation.claim.subject} -[{validation.claim.relationship}]-> "
                    f"{validation.claim.object}: supporting evidence missing"
                )
        for path in paths:
            if path.missing_evidence_count:
                missing.append(
                    f"Path {path.node_ids}: {path.missing_evidence_count} hop(s) lack provenance evidence"
                )
        return tuple(dict.fromkeys(missing))

    @staticmethod
    def _temporal_validity(
        validations: Iterable[ClaimValidation],
        paths: Iterable[InvestigationPath],
    ) -> str:
        checks = [validation.temporal_check for validation in validations]
        statuses = [path.temporally_valid for path in paths]
        statuses.extend(check.valid for check in checks if check is not None)
        if any(value is False for value in statuses):
            return TemporalValidity.INVALID
        if any(value is True for value in statuses):
            return TemporalValidity.VALID
        return TemporalValidity.UNKNOWN

    @staticmethod
    def _path_quality(paths: Iterable[InvestigationPath]) -> str:
        items = list(paths)
        if not items:
            return PathQuality.WEAK
        quality_points = []
        for path in items:
            if (
                path.temporally_valid is False
                or path.missing_evidence_count
                or path.conflicting_relationship_count
            ):
                quality_points.append((0, path.node_ids))
            elif (
                path.hop_count > 0
                and path.supporting_relationship_count == path.hop_count
            ):
                quality_points.append((2, path.node_ids))
            elif path.supporting_relationship_count > 0:
                quality_points.append((1, path.node_ids))
            else:
                quality_points.append((0, path.node_ids))
        best = max(quality_points)[0]
        return {2: PathQuality.STRONG, 1: PathQuality.MODERATE}.get(
            best, PathQuality.WEAK
        )

    @staticmethod
    def _path_quality_points(path: InvestigationPath) -> int:
        if path.temporally_valid is False:
            return -2
        points = 0
        if path.temporally_valid is True:
            points += 2
        if (
            path.missing_evidence_count == 0
            and path.conflicting_relationship_count == 0
        ):
            points += 1
        if path.hop_count > 0 and path.supporting_relationship_count == path.hop_count:
            points += 1
        return points

    @staticmethod
    def _unique_evidence(evidence: Iterable) -> tuple:
        by_id = {}
        for item in evidence:
            by_id[item.id] = item
        return tuple(by_id[key] for key in sorted(by_id))

    @staticmethod
    def _unique_strings(values: Iterable[str]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value for value in values if value))

    @staticmethod
    def _path_id(path: InvestigationPath) -> str:
        from continuum.hypothesis.model import path_id

        return path_id(path)
