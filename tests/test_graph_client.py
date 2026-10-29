import pytest

from continuum.graph import GraphClient


@pytest.mark.integration
def test_falkordb_is_reachable():
    client = GraphClient()
    assert client.ping() is True
