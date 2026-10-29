from __future__ import annotations

from continuum.graph.client import GraphClient
from continuum.graph.loader import WorldLoader
from domains.software.world import SOFTWARE_WORLD


def seed_software_world(client: GraphClient | None = None) -> GraphClient:
    """Load the authoritative M3/M4 software world through the universal loader."""
    client = client or GraphClient()
    return WorldLoader(client).load(SOFTWARE_WORLD, reset=True)


if __name__ == "__main__":
    seed_software_world()
    print("Seeded Continuum software investigation graph.")
