from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from continuum.core import EvidenceStatus, InvestigationResult, InvestigationState
from continuum.hypothesis import CompetitionOutcome, path_id
from continuum.report.model import (
    InvestigationReport,
    ReportPath,
    ReportSource,
    ReportStatement,
)
from continuum.validation import ClaimClassification, ClaimValidation


class GroundedReportBuilder:
    """Build an M11 report exclusively from an already-computed result/state."""

    def from_result(
        self,
        result: InvestigationResult,
    ) -> InvestigationReport:
        """Render an M6-M10 InvestigationResult without investigating."""

        if not isinstance(result, InvestigationResult):
            raise TypeError("result must be an InvestigationResult")

        return self._build(
            question=result.question,
            target=result.target,
            paths=result.candidate_paths,
            evidence=result.evidence,
            contradictions=result.contradictions,
            gaps=result.gaps,
            trace=result.trace,
            verdict=result.verdict,
            competition=None,
            state_hypotheses=(),
            validations=(),
        )

    def from_state(
        self,
        state: InvestigationState,
    ) -> InvestigationReport:
        """Render an M7/M10 state after investigation has completed.

        M11 requires the M10 competition boundary when rendering a state.
        The competition payload is consumed as data; it is never recomputed.
        """

        if not isinstance(state, InvestigationState):
            raise TypeError("state must be an InvestigationState")

        if "hypothesis_competition" not in state.extensions:
            raise ValueError(
                "InvestigationState is missing the M10 hypothesis_competition extension"
            )

        competition = state.extensions["hypothesis_competition"]

        if not isinstance(competition, dict):
            raise TypeError(
                "InvestigationState hypothesis_competition extension must be a dict"
            )

        verdict = competition.get("verdict")

        if not isinstance(verdict, str) or not verdict.strip():
            raise ValueError("M10 competition extension must contain a verdict")

        return self._build(
            question=state.question,
            target=state.target,
            paths=state.candidate_paths,
            evidence=state.evidence,
            contradictions=state.contradictions,
            gaps=state.gaps,
            trace=self._state_trace(state),
            verdict=verdict,
            competition=competition,
            state_hypotheses=state.hypotheses,
            validations=(),
        )

    def _build(
        self,
        *,
        question: str,
        target: str | None,
        paths: Iterable,
        evidence: Iterable,
        contradictions: Iterable[str],
        gaps: Iterable[str],
        trace: Iterable[str],
        verdict: str | None,
        competition: dict[str, Any] | None,
        state_hypotheses: Iterable,
        validations: Iterable[ClaimValidation],
    ) -> InvestigationReport:
        selected_paths = tuple(paths)

        selected_evidence = self._unique_evidence(
            evidence,
            selected_paths,
        )

        path_reports = tuple(self._path_report(path) for path in selected_paths)

        observed = self._observed_facts(selected_evidence)
        derived = self._derived_relationships(selected_paths)
        inferred = self._supported_inferences(validations)

        contradiction_items = self._unique_strings(contradictions)
        unknown_items = self._unique_strings(gaps)

        if competition is not None:
            competition_hypotheses = competition.get("hypotheses")

            if not isinstance(competition_hypotheses, list):
                raise ValueError("M10 competition extension has invalid hypotheses")

            explanation = self._explanation_from_competition(
                competition,
                competition_hypotheses,
            )

            contradiction_items = self._merge_competition_field(
                contradiction_items,
                competition_hypotheses,
                "contradictions",
            )

            unknown_items = self._merge_competition_field(
                unknown_items,
                competition_hypotheses,
                "missing_evidence",
            )

            path_reports = self._paths_for_competition(
                selected_paths,
                competition_hypotheses,
                competition,
            )
        else:
            explanation = self._explanation_from_result(
                verdict,
                selected_paths,
                target,
            )

        return InvestigationReport(
            question=question,
            verdict=verdict or "Insufficient evidence",
            most_supported_explanation=explanation,
            evidence_path=path_reports,
            observed_facts=observed,
            derived_relationships=derived,
            supported_inferences=inferred,
            contradictions=contradiction_items,
            unknowns=unknown_items,
            sources=self._sources(selected_evidence),
            investigation_trace=tuple(trace),
        )

    @staticmethod
    def _explanation_from_competition(
        competition: dict[str, Any],
        hypotheses: list[dict[str, Any]],
    ) -> str:
        outcome = competition.get("outcome")
        winner_ids = competition.get("winner_ids") or []

        by_id = {
            item.get("id"): item
            for item in hypotheses
            if isinstance(item, dict) and item.get("id")
        }

        if outcome == CompetitionOutcome.WINNER:
            if len(winner_ids) != 1 or winner_ids[0] not in by_id:
                raise ValueError("M10 winner outcome has no single matching hypothesis")

            item = by_id[winner_ids[0]]
            claim = item.get("claim")

            if not isinstance(claim, str) or not claim.strip():
                raise ValueError("M10 winning hypothesis has no claim")

            return claim

        if outcome == CompetitionOutcome.AMBIGUOUS:
            if len(winner_ids) < 2:
                raise ValueError("M10 ambiguous outcome needs multiple leaders")

            lines = ["Multiple explanations remain plausible."]

            for hypothesis_id in winner_ids:
                item = by_id.get(hypothesis_id)

                if item is None:
                    raise ValueError(
                        f"M10 ambiguous leader {hypothesis_id!r} is missing"
                    )

                lines.append(f"{hypothesis_id} — {item['claim']}")

            lines.append(
                "The available evidence does not justify selecting one over the other."
            )

            return "\n".join(lines)

        if outcome == CompetitionOutcome.INSUFFICIENT:
            return "Insufficient evidence."

        raise ValueError(f"Unsupported M10 competition outcome: {outcome!r}")

    @staticmethod
    def _explanation_from_result(
        verdict: str | None,
        paths: tuple,
        target: str | None,
    ) -> str:
        if verdict and verdict.strip():
            return verdict

        if paths:
            return (
                "A graph-derived path was found, but no M10 verdict "
                "is present; the available result does not justify "
                "selecting a winning explanation."
            )

        return "Insufficient evidence."

    @staticmethod
    def _path_report(path) -> ReportPath:
        return ReportPath(
            path_id=path_id(path),
            node_ids=path.node_ids,
            relationships=path.relationships,
            temporal_status=path.temporal_status,
            temporal_reason=path.temporal_reason,
            evidence_ids=tuple(item.id for item in path.evidence),
        )

    @staticmethod
    def _paths_for_competition(
        paths,
        hypotheses,
        competition,
    ) -> tuple[ReportPath, ...]:
        path_map = {path_id(path): path for path in paths}

        selected_ids: list[str] = []

        outcome = competition.get("outcome")
        leaders = set(competition.get("winner_ids") or [])

        for hypothesis in hypotheses:
            if not isinstance(hypothesis, dict) or hypothesis.get("id") not in leaders:
                continue

            selected_ids.extend(hypothesis.get("candidate_paths") or [])

        if outcome == CompetitionOutcome.INSUFFICIENT:
            selected_ids = [path_id(path) for path in paths]

        if not selected_ids:
            selected_ids = [path_id(path) for path in paths]

        unique = []
        seen = set()

        for identifier in selected_ids:
            if identifier in seen:
                continue

            seen.add(identifier)

            path = path_map.get(identifier)

            if path is not None:
                unique.append(GroundedReportBuilder._path_report(path))

        return tuple(unique)

    @staticmethod
    def _observed_facts(evidence) -> tuple[ReportStatement, ...]:
        statements = []

        for item in evidence:
            if item.status != EvidenceStatus.OBSERVED:
                continue

            detail = f"Observed evidence {item.id} from source {item.source_id}."

            if item.record:
                detail += f" Record: {item.record}."

            if item.span:
                detail += f" Span: {item.span}."

            statements.append(
                ReportStatement(
                    text=detail,
                    classification=ClaimClassification.OBSERVED,
                    evidence_ids=(item.id,),
                )
            )

        return tuple(statements)

    @staticmethod
    def _derived_relationships(paths) -> tuple[ReportStatement, ...]:
        statements = []
        seen = set()

        for path in paths:
            identifier = path_id(path)

            for subject, relationship, target in zip(
                path.node_ids[:-1],
                path.relationships,
                path.node_ids[1:],
                strict=True,
            ):
                key = (
                    subject,
                    relationship,
                    target,
                )

                if key in seen:
                    continue

                seen.add(key)

                statements.append(
                    ReportStatement(
                        text=(f"{subject} -[{relationship}]-> {target}"),
                        classification=ClaimClassification.DERIVED,
                        path_ids=(identifier,),
                    )
                )

        return tuple(statements)

    @staticmethod
    def _supported_inferences(
        validations: Iterable[ClaimValidation],
    ) -> tuple[ReportStatement, ...]:
        statements = []

        for validation in validations:
            if validation.classification != ClaimClassification.SUPPORTED_INFERENCE:
                continue

            claim = validation.claim

            statements.append(
                ReportStatement(
                    text=(f"{claim.subject} -[{claim.relationship}]-> {claim.object}"),
                    classification=(ClaimClassification.SUPPORTED_INFERENCE),
                    evidence_ids=tuple(item.id for item in validation.evidence),
                )
            )

        return tuple(statements)

    @staticmethod
    def _sources(evidence) -> tuple[ReportSource, ...]:
        sources = []
        seen = set()

        for item in sorted(
            evidence,
            key=lambda value: (
                value.source_id,
                value.id,
            ),
        ):
            if item.source_id in seen:
                continue

            seen.add(item.source_id)

            name = str(item.metadata.get("name") or item.source_id)

            sources.append(
                ReportSource(
                    id=item.source_id,
                    name=name,
                    status=item.status,
                    observed_at=item.observed_at,
                    record=item.record,
                    span=item.span,
                )
            )

        return tuple(sources)

    @staticmethod
    def _unique_evidence(evidence, paths):
        items = list(evidence)

        items.extend(item for path in paths for item in path.evidence)

        by_id = {}

        for item in items:
            by_id[item.id] = item

        return tuple(by_id[key] for key in sorted(by_id))

    @staticmethod
    def _unique_strings(values) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value for value in values if value))

    @staticmethod
    def _merge_competition_field(
        base,
        hypotheses,
        field,
    ) -> tuple[str, ...]:
        values = list(base)

        for hypothesis in hypotheses:
            if isinstance(hypothesis, dict):
                values.extend(hypothesis.get(field) or [])

        return tuple(dict.fromkeys(value for value in values if value))

    @staticmethod
    def _state_trace(
        state: InvestigationState,
    ) -> tuple[str, ...]:
        trace: list[str] = []

        for step in state.history:
            trace.append(f"step_{step.state_version}={step.operation}")

            trace.extend(step.result.trace)

        return tuple(dict.fromkeys(trace))


ReportBuilder = GroundedReportBuilder
