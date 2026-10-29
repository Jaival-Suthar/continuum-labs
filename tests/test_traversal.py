import pytest

from continuum.graph import GraphClient, GraphTraversal
from continuum.graph.seed import seed_software_world


@pytest.fixture
def traversal():
    return GraphTraversal(seed_software_world(GraphClient()))


@pytest.mark.integration
def test_find_node(traversal):
    rows = traversal.find_by_id("incident-001")
    assert rows
    assert rows[0][1] == "incident-001"


@pytest.mark.integration
def test_find_neighbors(traversal):
    rows = traversal.neighbors("dependency-gateway-sdk")

    assert rows
    assert [
        row for row in rows if row[1] == "DEPENDS_ON" and row[2] == "service-payments"
    ]


@pytest.mark.integration
def test_find_multi_hop_path(traversal):
    rows = traversal.paths_between("commit-001", "incident-001")

    assert rows

    nodes, relationships = rows[0]

    assert [node.properties["id"] for node in nodes] == [
        "commit-001",
        "dependency-gateway-sdk",
        "service-payments",
        "deployment-001",
        "metric-001",
        "incident-001",
    ]

    assert [edge.relation for edge in relationships] == [
        "CHANGED",
        "DEPENDS_ON",
        "AFFECTS",
        "AFFECTS",
        "RESULTED_IN",
    ]


@pytest.mark.integration
def test_find_preceding_events(traversal):
    rows = traversal.preceding("incident-001", "2026-08-01T10:00:00Z")

    assert rows
    assert all(row[3] < "2026-08-01T10:00:00Z" for row in rows)


@pytest.mark.integration
def test_relationship_evidence(traversal):
    rows = traversal.relationship_evidence(
        "commit-001",
        "dependency-gateway-sdk",
    )

    assert rows
    assert rows[0][0] == "CHANGED"
    assert rows[0][1]["timestamp"] == "2026-08-01T09:00:00Z"
    assert rows[0][2] == ["source-commit"]
