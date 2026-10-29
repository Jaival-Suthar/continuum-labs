import pytest

from continuum.graph import GraphClient, WorldLoader
from domains.software.world import SOFTWARE_WORLD
from domains.supply_chain.world import SUPPLY_CHAIN_WORLD


@pytest.mark.integration
def test_same_loader_can_load_both_worlds():
    client = GraphClient()
    loader = WorldLoader(client)

    loader.load(SOFTWARE_WORLD, reset=True)
    software = client.read("MATCH (n) RETURN count(n)")
    assert software.result_set[0][0] == len(SOFTWARE_WORLD.data.nodes())

    loader.load(SUPPLY_CHAIN_WORLD, reset=True)
    supply = client.read("MATCH (n) RETURN count(n)")
    assert supply.result_set[0][0] == len(SUPPLY_CHAIN_WORLD.data.nodes())
