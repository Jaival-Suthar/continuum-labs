from __future__ import annotations

import pytest

from continuum.graph.client import GraphClient, GraphConfig
from continuum.graph.loader import WorldLoader
from continuum.investigator import Investigator
from domains.software.world import SOFTWARE_WORLD
from domains.supply_chain.world import SUPPLY_CHAIN_WORLD


@pytest.mark.integration
def test_m15_question_resolves_and_uses_universal_investigator():
    graph = GraphClient(GraphConfig(graph_name="continuum-m15-pytest"))
    graph.ping()
    WorldLoader(graph).load(SUPPLY_CHAIN_WORLD, reset=True)
    investigator = Investigator(graph, SUPPLY_CHAIN_WORLD)
    result = investigator.investigate("Why was Customer X affected?")
    assert result.target == "impact-001"
    assert type(investigator) is type(Investigator(graph, SOFTWARE_WORLD))


@pytest.mark.integration
def test_m15_primary_alternative_and_conflict_paths():
    graph = GraphClient(GraphConfig(graph_name="continuum-m15-pytest"))
    WorldLoader(graph).load(SUPPLY_CHAIN_WORLD, reset=True)
    investigator = Investigator(graph, SUPPLY_CHAIN_WORLD)

    primary = investigator.find_paths(
        "supplier-001", "impact-001", max_hops=6, limit=25
    )
    alternative = investigator.find_paths(
        "supplier-002", "impact-001", max_hops=6, limit=25
    )
    conflict = investigator.find_paths(
        "supplier-003", "impact-001", max_hops=6, limit=25
    )

    p = next(path for path in primary if path.temporally_valid is True)
    a = next(path for path in alternative if path.temporally_valid is True)
    c = next(path for path in conflict if path.temporally_valid is False)
    assert p.hop_count == 6 and len(p.evidence) == 6
    assert a.hop_count == 6 and len(a.evidence) == 6
    assert c.hop_count == 6
