from typing import ClassVar

import pytest

from continuum.core import Ontology
from continuum.graph.schema import CORE_LABELS, CORE_RELATIONSHIPS, GraphSchema


def test_core_schema_contains_universal_objects():
    assert {"Entity", "Event", "Change", "Observation", "Outcome", "Source"} <= set(
        CORE_LABELS
    )


def test_core_schema_contains_investigation_relationships():
    assert {"AFFECTS", "DEPENDS_ON", "SUPPORTED_BY", "PRECEDED"} <= set(
        CORE_RELATIONSHIPS
    )


def test_schema_accepts_domain_extensions():
    schema = GraphSchema(Ontology(name="software", label_extensions=("Commit",)))
    schema.validate_label("Commit")
    schema.validate_relationship("DEPENDS_ON")


def test_schema_rejects_unknown_relationship():
    with pytest.raises(ValueError):
        GraphSchema().validate_relationship("CAUSES")


def test_schema_rejects_unknown_label():
    with pytest.raises(ValueError):
        GraphSchema().validate_label("Commit")


class FakeSchemaResult:
    result_set: ClassVar[list] = []


class FakeSchemaGraph:
    def __init__(self):
        self.queries = []

    def query(self, cypher, params=None):
        self.queries.append((cypher, params))
        return FakeSchemaResult()


def test_schema_initializes_indexes_for_core_and_domain_labels():
    graph = FakeSchemaGraph()
    schema = GraphSchema(Ontology(name="software", label_extensions=("Commit",)))

    schema.initialize(graph)

    create_queries = [
        query for query, _ in graph.queries if query.startswith("CREATE INDEX")
    ]
    assert len(create_queries) == len(schema.labels)
    assert any(":Entity" in query for query in create_queries)
    assert any(":Commit" in query for query in create_queries)
