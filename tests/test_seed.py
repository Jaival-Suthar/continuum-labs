import pytest

from continuum.graph import GraphClient
from continuum.graph.seed import seed_software_world


@pytest.mark.integration
def test_seed_creates_expected_software_chain():
    client = seed_software_world(GraphClient())
    result = client.read(
        "MATCH (c:Commit {id:'commit-001'})-[:CHANGED]->"
        "(d:Dependency {id:'dependency-gateway-sdk'}) "
        "RETURN c.id, d.id"
    )
    assert result.result_set
    assert result.result_set[0][0] == "commit-001"
    assert result.result_set[0][1] == "dependency-gateway-sdk"
