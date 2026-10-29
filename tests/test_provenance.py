import pytest

from continuum.graph import GraphClient
from continuum.graph.provenance import relationship_with_evidence
from continuum.graph.seed import seed_software_world


@pytest.mark.integration
def test_relationship_provenance_is_retrievable():
    client = seed_software_world(GraphClient())
    relationships = relationship_with_evidence(
        client, "commit-001", "dependency-gateway-sdk"
    )

    assert relationships
    relationship = relationships[0]

    assert relationship.source_id == "commit-001"
    assert relationship.relationship == "CHANGED"
    assert relationship.target_id == "dependency-gateway-sdk"
    assert relationship.evidence_source_ids == ("source-commit-001",)
    assert relationship.evidence_status == "OBSERVED"
    assert relationship.evidence[0].record == "abc123"
    assert relationship.evidence[0].span == "commit abc123"
