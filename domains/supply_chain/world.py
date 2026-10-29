from continuum.core.ontology import TemporalModel
from continuum.core.world import World
from domains.supply_chain.data import SUPPLY_CHAIN_DATA
from domains.supply_chain.ontology import SUPPLY_CHAIN_ONTOLOGY

SUPPLY_CHAIN_WORLD = World(
    name="supply-chain",
    ontology=SUPPLY_CHAIN_ONTOLOGY,
    data=SUPPLY_CHAIN_DATA,
    temporal_model=TemporalModel(),
)
