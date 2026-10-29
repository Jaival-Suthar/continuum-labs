from __future__ import annotations

from typing import Any

from continuum.core.models import GraphEdge, GraphNode
from continuum.core.world import World
from continuum.graph.client import GraphClient
from continuum.graph.schema import GraphSchema


class WorldLoader:
    """Load any validated World through the universal graph contract."""

    def __init__(self, client: GraphClient):
        self.client = client

    def initialize(self, world: World) -> None:
        world.validate()
        GraphSchema(world.ontology).initialize(self.client)

    def load(self, world: World, *, reset: bool = False) -> GraphClient:
        """Reset, initialize, and load a world into the graph."""
        world.validate()

        if reset:
            self.client.reset()

        self.initialize(world)

        for node in world.data.nodes():
            self._load_node(world, node)
        for edge in world.data.edges():
            self._load_edge(world, edge)
        return self.client

    @staticmethod
    def _temporal_properties(item: GraphNode | GraphEdge) -> dict[str, str]:
        properties: dict[str, str] = {}
        for field_name in ("timestamp", "valid_from", "valid_until", "observed_at"):
            value = getattr(item, field_name, None)
            if value is not None:
                properties[field_name] = value.isoformat().replace("+00:00", "Z")
        return properties

    def _load_node(self, world: World, node: GraphNode) -> None:
        world.ontology.validate_label(node.label)
        properties: dict[str, Any] = dict(node.properties)
        properties.pop("id", None)
        properties.update(self._temporal_properties(node))
        properties["name"] = node.name

        self.client.query(
            f"""
            MERGE (n:{node.label} {{id: $id}})
            SET n += $properties
            """,
            {"id": node.id, "properties": properties},
        )

    def _load_edge(self, world: World, edge: GraphEdge) -> None:
        world.ontology.validate_relationship(edge.relationship)

        properties: dict[str, Any] = dict(edge.properties)
        properties.pop("edge_id", None)
        properties.update(self._temporal_properties(edge))
        properties["edge_id"] = edge.stable_id
        properties["evidence_status"] = edge.evidence_status
        properties["evidence_source_ids"] = list(edge.evidence_source_ids)
        properties["provenance_version"] = 1

        self.client.query(
            f"""
            MATCH (source {{id: $source_id}}), (target {{id: $target_id}})
            MERGE (source)-[r:{edge.relationship} {{edge_id: $edge_id}}]->(target)
            SET r += $properties
            """,
            {
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "edge_id": edge.stable_id,
                "properties": properties,
            },
        )
