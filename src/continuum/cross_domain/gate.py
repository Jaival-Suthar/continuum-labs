from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

from continuum.core import Hypothesis, InvestigationResult, InvestigationState, World
from continuum.hypothesis import HypothesisCompetitionResult, path_id
from continuum.investigator import Investigator
from continuum.report import GroundedReportBuilder
from continuum.validation import ClaimClassification


@dataclass(frozen=True)
class DomainGateSpec:
    """Deterministic fixture contract for one side of the M16 gate."""

    name: str
    world: World
    question: str
    target_id: str
    primary_path: tuple[str, ...]
    alternative_path: tuple[str, ...] | None = None
    conflict_path: tuple[str, ...] | None = None


@dataclass(frozen=True)
class DomainGateResult:
    """Auditable output from one real FalkorDB-backed M16 investigation."""

    name: str
    question: str
    target: str
    primary_path: tuple[str, ...]
    primary_hops: int
    primary_evidence_count: int
    primary_temporally_valid: bool
    alternative_path: tuple[str, ...] | None
    alternative_temporally_valid: bool | None
    conflict_path: tuple[str, ...] | None
    conflict_temporally_valid: bool | None
    investigation_trace: tuple[str, ...]
    hypothesis: HypothesisCompetitionResult
    report: Any


@dataclass(frozen=True)
class CrossDomainGateResult:
    """Complete M16 gate result, including shared implementation identity."""

    software: DomainGateResult
    supply_chain: DomainGateResult
    shared_implementations: dict[str, bool]
    shared_implementation_types: dict[str, str]
    no_domain_specific_investigator_branches: bool

    @property
    def passed(self) -> bool:
        return (
            all(self.shared_implementations.values())
            and self.no_domain_specific_investigator_branches
        )

    def as_dict(self) -> dict[str, Any]:
        def domain_dict(item: DomainGateResult) -> dict[str, Any]:
            return {
                "status": "PASS",
                "question": item.question,
                "target": item.target,
                "primary_path": list(item.primary_path),
                "primary_hops": item.primary_hops,
                "primary_evidence_count": item.primary_evidence_count,
                "primary_temporally_valid": item.primary_temporally_valid,
                "alternative_path": list(item.alternative_path)
                if item.alternative_path
                else None,
                "alternative_temporally_valid": item.alternative_temporally_valid,
                "conflict_path": list(item.conflict_path)
                if item.conflict_path
                else None,
                "conflict_temporally_valid": item.conflict_temporally_valid,
                "hypothesis": item.hypothesis.as_dict(),
                "report": item.report.as_dict(),
                "investigation_trace": list(item.investigation_trace),
            }

        return {
            "software": domain_dict(self.software),
            "supply_chain": domain_dict(self.supply_chain),
            "shared_implementations": dict(self.shared_implementations),
            "shared_implementation_types": dict(self.shared_implementation_types),
            "no_domain_specific_investigator_branches": self.no_domain_specific_investigator_branches,
            "status": "PASS" if self.passed else "FAIL",
        }


def _find_path(paths, expected_node_ids: tuple[str, ...]):
    for path in paths:
        if path.node_ids == expected_node_ids:
            return path
    raise AssertionError(f"Expected path not found: {expected_node_ids}")


def _run_hypothesis_workflow(
    investigator: Investigator,
    *,
    question: str,
    target: str,
    primary,
    alternative,
    hypothesis_ids: tuple[str, str],
) -> tuple[HypothesisCompetitionResult, InvestigationState]:
    """Exercise the shared M7/M10 machinery using actual graph-derived paths."""
    state = investigator.start_investigation(question, target_id=target)
    state.merge_result(
        InvestigationResult(
            question=question,
            target=target,
            candidate_paths=[
                primary,
                *([alternative] if alternative is not None else []),
            ],
            evidence=[
                evidence
                for path in (
                    primary,
                    *([alternative] if alternative is not None else []),
                )
                for evidence in path.evidence
            ],
        ),
        operation="cross_domain_paths",
    )

    state.add_hypothesis(
        Hypothesis(
            id=hypothesis_ids[0],
            description="Primary graph-derived explanation",
            candidate_path_ids=(path_id(primary),),
            evidence_ids=tuple(item.id for item in primary.evidence),
        )
    )

    if alternative is not None:
        state.add_hypothesis(
            Hypothesis(
                id=hypothesis_ids[1],
                description="Alternative graph-derived explanation",
                candidate_path_ids=(path_id(alternative),),
                evidence_ids=tuple(item.id for item in alternative.evidence),
            )
        )
    else:
        state.add_hypothesis(
            Hypothesis(
                id=hypothesis_ids[1],
                description="Alternative explanation with no recovered path",
            )
        )

    competition = investigator.compete_hypotheses(state)
    state.extensions["hypothesis_competition"] = competition.as_dict()
    return competition, state


def _run_domain(
    investigator: Investigator,
    spec: DomainGateSpec,
) -> DomainGateResult:
    """Load-independent portion of M16; all graph work is done by Investigator."""
    result = investigator.investigate(spec.question, world=spec.world)
    assert result.target == spec.target_id, (
        f"{spec.name}: expected target {spec.target_id!r}, got {result.target!r}"
    )

    primary = _find_path(
        investigator.find_paths(
            spec.primary_path[0], spec.target_id, max_hops=6, limit=25
        ),
        spec.primary_path,
    )
    assert primary.temporally_valid is True, (
        f"{spec.name}: primary path is not temporally valid: {primary.temporal_status}"
    )
    assert primary.hop_count == len(spec.primary_path) - 1
    assert len(primary.evidence) == primary.hop_count
    assert primary.supporting_relationship_count == primary.hop_count

    alternative = None
    if spec.alternative_path is not None:
        alternative = _find_path(
            investigator.find_paths(
                spec.alternative_path[0],
                spec.target_id,
                max_hops=6,
                limit=25,
            ),
            spec.alternative_path,
        )
        assert alternative.temporally_valid is True, (
            f"{spec.name}: alternative path is not temporally valid: "
            f"{alternative.temporal_status}"
        )

    conflict = None
    if spec.conflict_path is not None:
        conflict = _find_path(
            investigator.find_paths(
                spec.conflict_path[0],
                spec.target_id,
                max_hops=6,
                limit=25,
            ),
            spec.conflict_path,
        )
        assert conflict.temporally_valid is False, (
            f"{spec.name}: expected conflict path to be temporally invalid"
        )

    second = alternative
    competition, state = _run_hypothesis_workflow(
        investigator,
        question=spec.question,
        target=spec.target_id,
        primary=primary,
        alternative=second,
        hypothesis_ids=("H1", "H2"),
    )

    assert state.target == spec.target_id
    assert all(
        isinstance(item, InvestigationResult)
        for item in (step.result for step in state.history)
    )
    assert all(
        validation.classification in ClaimClassification.ALL
        for hypothesis in competition.hypotheses
        for validation in hypothesis.claim_validations
    )

    report = GroundedReportBuilder().from_state(state)
    assert report.evidence_path
    assert report.sources
    assert report.investigation_trace

    return DomainGateResult(
        name=spec.name,
        question=spec.question,
        target=result.target,
        primary_path=primary.node_ids,
        primary_hops=primary.hop_count,
        primary_evidence_count=len(primary.evidence),
        primary_temporally_valid=primary.temporally_valid is True,
        alternative_path=alternative.node_ids if alternative else None,
        alternative_temporally_valid=(
            alternative.temporally_valid if alternative else None
        ),
        conflict_path=conflict.node_ids if conflict else None,
        conflict_temporally_valid=(conflict.temporally_valid if conflict else None),
        investigation_trace=tuple(result.trace),
        hypothesis=competition,
        report=report,
    )


def shared_implementation_identity() -> dict[str, bool]:
    """Verify that the graph/state/hypothesis/validation/report layers are shared."""
    from continuum.graph.traversal import GraphTraversal
    from continuum.hypothesis import HypothesisEvaluator
    from continuum.report import GroundedReportBuilder
    from continuum.temporal import TemporalQueries
    from continuum.validation import EvidenceValidator

    return {
        "investigator": Investigator.__module__ == "continuum.investigator.engine"
        and Investigator.__qualname__ == "Investigator",
        "graph_operations": GraphTraversal.__module__ == "continuum.graph.traversal"
        and TemporalQueries.__module__ == "continuum.temporal.queries",
        "state_model": InvestigationState.__module__ == "continuum.core.models",
        "hypothesis_system": HypothesisEvaluator.__module__
        == "continuum.hypothesis.evaluator",
        "validation": EvidenceValidator.__module__ == "continuum.validation.validator",
        "reporting": GroundedReportBuilder.__module__ == "continuum.report.builder",
    }


def shared_implementation_types() -> dict[str, str]:
    """Return qualified implementation names recorded by the M16 artifact."""
    from continuum.graph.traversal import GraphTraversal
    from continuum.hypothesis import HypothesisEvaluator
    from continuum.report import GroundedReportBuilder
    from continuum.temporal import TemporalQueries
    from continuum.validation import EvidenceValidator

    classes = {
        "investigator": Investigator,
        "graph_operations": GraphTraversal,
        "temporal_operations": TemporalQueries,
        "state_model": InvestigationState,
        "result_model": InvestigationResult,
        "hypothesis_system": HypothesisEvaluator,
        "validation": EvidenceValidator,
        "reporting": GroundedReportBuilder,
    }
    return {
        name: f"{cls.__module__}.{cls.__qualname__}" for name, cls in classes.items()
    }


def has_domain_specific_investigator_branches() -> bool:
    """Reject a future Investigator that directly names either V1 domain."""
    source = inspect.getsource(Investigator).lower()
    forbidden = (
        "software_world",
        "supply_chain_world",
        "softwareinvestigator",
        "supplychaininvestigator",
        "investigate_software",
        "investigate_supply_chain",
    )
    return any(token in source for token in forbidden)


def run_cross_domain_gate(
    graph,
    *,
    software: DomainGateSpec,
    supply_chain: DomainGateSpec,
) -> CrossDomainGateResult:
    """Run both worlds through one Investigator instance and return the gate."""
    from continuum.graph.loader import WorldLoader

    investigator = Investigator(graph, software.world)

    WorldLoader(graph).load(software.world, reset=True)
    software_result = _run_domain(investigator, software)

    WorldLoader(graph).load(supply_chain.world, reset=True)
    supply_result = _run_domain(investigator, supply_chain)

    shared = shared_implementation_identity()
    implementation_types = shared_implementation_types()
    no_domain_branches = not has_domain_specific_investigator_branches()

    gate = CrossDomainGateResult(
        software=software_result,
        supply_chain=supply_result,
        shared_implementations=shared,
        shared_implementation_types=implementation_types,
        no_domain_specific_investigator_branches=no_domain_branches,
    )
    assert gate.passed, "M16 shared-implementation gate failed"
    return gate
