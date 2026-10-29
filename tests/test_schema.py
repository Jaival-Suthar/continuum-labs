import pytest

from continuum.graph.schema import CORE_LABELS, CORE_RELATIONSHIPS, GraphSchema


def test_core_schema_contains_universal_objects():
    assert {"Entity", "Event", "Change", "Observation", "Outcome", "Source"} <= set(
        CORE_LABELS
    )


def test_core_schema_contains_investigation_relationships():
    assert {"AFFECTS", "DEPENDS_ON", "SUPPORTED_BY", "PRECEDED"} <= set(
        CORE_RELATIONSHIPS
    )


def test_schema_rejects_unknown_relationship():
    with pytest.raises(ValueError):
        GraphSchema().validate_relationship("CAUSES")
