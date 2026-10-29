from __future__ import annotations

from continuum.graph.client import GraphClient
from continuum.graph.schema import GraphSchema


def initialize_graph(client: GraphClient | None = None) -> GraphClient:
    client = client or GraphClient()
    GraphSchema().initialize(client)
    return client


if __name__ == "__main__":
    initialize_graph()
    print("Continuum graph schema initialized.")
