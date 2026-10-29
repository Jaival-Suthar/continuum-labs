from datetime import UTC, datetime

import pytest

from continuum.core import (
    CORE_LABELS,
    CORE_RELATIONSHIPS,
    GraphEdge,
    GraphNode,
    Ontology,
    TemporalModel,
    World,
)
from continuum.investigator.engine import Investigator
from domains.software.world import SOFTWARE_WORLD
from domains.supply_chain.world import SUPPLY_CHAIN_WORLD


def test_core_ontology_contains_required_universal_objects_and_relationships():
    assert {
        "Entity",
        "Event",
        "Change",
        "Observation",
        "Outcome",
        "Source",
    } <= set(CORE_LABELS)
    assert {
        "AFFECTS",
        "DEPENDS_ON",
        "CHANGED",
        "PRECEDED",
        "RESULTED_IN",
        "OBSERVED_AS",
        "SUPPORTED_BY",
        "MENTIONED_IN",
        "OWNED_BY",
    } <= set(CORE_RELATIONSHIPS)


def test_core_models_represent_temporal_metadata_and_provenance():
    timestamp = datetime(2026, 8, 1, 9, tzinfo=UTC)
    node = GraphNode(
        "change-1",
        "Change",
        "gateway update",
        timestamp=timestamp,
        valid_from=timestamp,
        properties={"author": "example"},
    )
    edge = GraphEdge(
        "change-1",
        "CHANGED",
        "dependency-1",
        timestamp=timestamp,
        evidence_source_ids=("source-1",),
    )

    assert node.timestamp == timestamp
    assert node.properties["author"] == "example"
    assert edge.evidence_source_ids == ("source-1",)


def test_core_models_reject_invalid_identity_and_temporal_ranges():
    with pytest.raises(ValueError, match="id"):
        GraphNode("", "Entity", "A")

    with pytest.raises(ValueError, match="name"):
        GraphNode("a", "Entity", "")

    timestamp = datetime(2026, 8, 2, tzinfo=UTC)
    with pytest.raises(ValueError, match="valid_from"):
        GraphNode(
            "a",
            "Entity",
            "A",
            valid_from=timestamp,
            valid_until=timestamp.replace(day=1),
        )


def test_ontology_supports_domain_extensions_without_replacing_core():
    ontology = Ontology(
        name="software",
        label_extensions=("Commit",),
        relationship_extensions=("DEPENDS_ON_RUNTIME",),
    )

    assert "Entity" in ontology.all_labels
    assert "Commit" in ontology.all_labels
    assert "DEPENDS_ON" in ontology.all_relationships
    assert "DEPENDS_ON_RUNTIME" in ontology.all_relationships

    ontology.validate_label("Commit")
    ontology.validate_relationship("DEPENDS_ON_RUNTIME")

    with pytest.raises(ValueError):
        ontology.validate_label("NotARealLabel")


def test_world_validation_is_domain_independent():
    SOFTWARE_WORLD.validate()
    SUPPLY_CHAIN_WORLD.validate()


def test_world_rejects_unknown_edge_endpoint():
    class Data:
        def nodes(self):
            return (GraphNode("a", "Entity", "A"),)

        def edges(self):
            return (GraphEdge("a", "AFFECTS", "missing"),)

    world = World(
        name="invalid",
        ontology=Ontology(name="invalid"),
        data=Data(),
    )

    with pytest.raises(ValueError, match="Unknown edge target"):
        world.validate()


def test_world_rejects_duplicate_node_ids():
    class Data:
        def nodes(self):
            return (
                GraphNode("a", "Entity", "A"),
                GraphNode("a", "Entity", "A2"),
            )

        def edges(self):
            return ()

    with pytest.raises(ValueError, match="Duplicate node id"):
        World("invalid", Ontology("invalid"), Data()).validate()


def test_world_rejects_unsupported_temporal_operations():
    class Data:
        def nodes(self):
            return ()

        def edges(self):
            return ()

    temporal = TemporalModel(operations=("before", "not_a_operation"))
    with pytest.raises(ValueError, match="temporal model"):
        World("invalid", Ontology("invalid"), Data(), temporal).validate()


def test_world_rejects_unsupported_temporal_fields():
    class Data:
        def nodes(self):
            return ()

        def edges(self):
            return ()

    temporal = TemporalModel(fields=("timestamp", "not_a_field"))
    with pytest.raises(ValueError, match="temporal model"):
        World("invalid", Ontology("invalid"), Data(), temporal).validate()


def test_domain_extensions_are_available_in_both_worlds():
    software_labels = {node.label for node in SOFTWARE_WORLD.data.nodes()}
    supply_labels = {node.label for node in SUPPLY_CHAIN_WORLD.data.nodes()}

    assert {"Commit", "Dependency", "Service", "Deployment"} <= software_labels
    assert {"Supplier", "Component", "Factory", "Shipment"} <= supply_labels


def test_same_investigator_accepts_both_worlds_without_domain_selector():
    investigator = Investigator(graph=object())

    software_result = investigator.investigate(
        "Why did the software incident happen?",
        world=SOFTWARE_WORLD,
    )
    supply_result = investigator.investigate(
        "Why was the customer affected?",
        world=SUPPLY_CHAIN_WORLD,
    )

    assert software_result.question.startswith("Why did")
    assert "world=software" in software_result.trace
    assert "world=supply-chain" in supply_result.trace
