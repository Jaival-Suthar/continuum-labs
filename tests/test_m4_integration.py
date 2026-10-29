import pytest

from continuum.graph import GraphClient, WorldLoader
from continuum.graph.provenance import relationship_with_evidence
from domains.software.world import SOFTWARE_WORLD


@pytest.fixture
def software_graph():
    client = GraphClient()
    WorldLoader(client).load(SOFTWARE_WORLD, reset=True)
    return client


@pytest.mark.integration
def test_primary_relationship_provenance_is_resolvable(software_graph):
    relationships = relationship_with_evidence(
        software_graph,
        "commit-001",
        "dependency-gateway-sdk",
    )

    assert len(relationships) == 1
    relationship = relationships[0]

    assert relationship.edge_id
    assert relationship.evidence_status == "OBSERVED"
    assert relationship.evidence_source_ids == ("source-commit-001",)
    assert len(relationship.evidence) == 1

    evidence = relationship.evidence[0]
    assert evidence.source_id == "source-commit-001"
    assert evidence.status == "OBSERVED"
    assert evidence.record == "abc123"
    assert evidence.span == "commit abc123"
    assert evidence.observed_at is not None


@pytest.mark.integration
def test_missing_hypothesis_evidence_is_explicit(software_graph):
    relationships = relationship_with_evidence(
        software_graph,
        "infra-event-001",
        "metric-001",
    )

    assert len(relationships) == 1
    relationship = relationships[0]

    assert relationship.edge_id
    assert relationship.evidence_status == "UNKNOWN"
    assert relationship.evidence_source_ids == ()
    assert relationship.evidence == ()
