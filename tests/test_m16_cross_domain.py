from __future__ import annotations

import inspect

from continuum.core import InvestigationResult, InvestigationState
from continuum.cross_domain import (
    DomainGateSpec,
    has_domain_specific_investigator_branches,
    shared_implementation_identity,
    shared_implementation_types,
)
from continuum.hypothesis import HypothesisEvaluator
from continuum.investigator import Investigator
from continuum.report import GroundedReportBuilder
from continuum.validation import EvidenceValidator
from continuum.graph.traversal import GraphTraversal
from continuum.temporal import TemporalQueries
from domains.software.world import SOFTWARE_WORLD
from domains.supply_chain.world import SUPPLY_CHAIN_WORLD


def test_m16_worlds_validate_through_same_world_contract():
    SOFTWARE_WORLD.validate()
    SUPPLY_CHAIN_WORLD.validate()
    assert type(SOFTWARE_WORLD) is type(SUPPLY_CHAIN_WORLD)


def test_m16_same_investigator_implementation():
    assert type(Investigator(object())) is type(Investigator(object()))
    assert Investigator.__module__ == "continuum.investigator.engine"
    assert Investigator.__qualname__ == "Investigator"
    assert not has_domain_specific_investigator_branches()


def test_m16_shared_layer_identity_is_explicit():
    identity = shared_implementation_identity()
    assert identity == {
        "investigator": True,
        "graph_operations": True,
        "state_model": True,
        "hypothesis_system": True,
        "validation": True,
        "reporting": True,
    }


def test_m16_shared_types_are_not_domain_subclasses():
    assert GraphTraversal.__module__ == "continuum.graph.traversal"
    assert TemporalQueries.__module__ == "continuum.temporal.queries"
    assert InvestigationState.__module__ == "continuum.core.models"
    assert InvestigationResult.__module__ == "continuum.core.models"
    assert HypothesisEvaluator.__module__ == "continuum.hypothesis.evaluator"
    assert EvidenceValidator.__module__ == "continuum.validation.validator"
    assert GroundedReportBuilder.__module__ == "continuum.report.builder"


def test_m16_domain_specs_contain_no_investigator_logic():
    software = DomainGateSpec(
        "software",
        SOFTWARE_WORLD,
        "Why did incident-001 happen?",
        "incident-001",
        ("commit-001", "dependency-gateway-sdk", "service-payments", "deployment-001", "metric-001", "incident-001"),
    )
    supply = DomainGateSpec(
        "supply_chain",
        SUPPLY_CHAIN_WORLD,
        "Why was Customer X affected?",
        "impact-001",
        ("supplier-001", "component-001", "factory-001", "shipment-001", "warehouse-001", "account-001", "impact-001"),
    )
    assert software.world is SOFTWARE_WORLD
    assert supply.world is SUPPLY_CHAIN_WORLD
    assert inspect.isclass(Investigator)


def test_m16_artifact_records_qualified_shared_implementations():
    types = shared_implementation_types()
    assert types["investigator"] == "continuum.investigator.engine.Investigator"
    assert types["graph_operations"] == "continuum.graph.traversal.GraphTraversal"
    assert types["temporal_operations"] == "continuum.temporal.queries.TemporalQueries"
    assert types["state_model"] == "continuum.core.models.InvestigationState"
    assert types["result_model"] == "continuum.core.models.InvestigationResult"
    assert types["hypothesis_system"] == "continuum.hypothesis.evaluator.HypothesisEvaluator"
    assert types["validation"] == "continuum.validation.validator.EvidenceValidator"
    assert types["reporting"] == "continuum.report.builder.GroundedReportBuilder"
