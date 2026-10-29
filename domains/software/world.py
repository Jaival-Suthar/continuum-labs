from continuum.core.ontology import TemporalModel
from continuum.core.world import World
from domains.software.data import SOFTWARE_DATA
from domains.software.ontology import SOFTWARE_ONTOLOGY

SOFTWARE_WORLD = World(
    name="software",
    ontology=SOFTWARE_ONTOLOGY,
    data=SOFTWARE_DATA,
    temporal_model=TemporalModel(),
)
