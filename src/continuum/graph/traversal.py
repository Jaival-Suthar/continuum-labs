from __future__ import annotations

from typing import Any

from continuum.graph.client import GraphClient


class GraphTraversal:
    """Deterministic graph primitives used by the future investigator."""

    def __init__(self, client: GraphClient):
        self.client = client

    def find_by_id(self, node_id: str) -> list[list[Any]]:
        result = self.client.read(
            "MATCH (n {id:$node_id}) RETURN labels(n), n.id, n.name, n.timestamp",
            {"node_id": node_id},
        )
        return result.result_set

    def neighbors(self, node_id: str) -> list[list[Any]]:
        result = self.client.read(
            """
            MATCH (n {id:$node_id})-[r]-(m)
            RETURN n.id, type(r), m.id, labels(m), m.name
            ORDER BY m.id
            """,
            {"node_id": node_id},
        )
        return result.result_set

    def paths_between(
        self, start_id: str, end_id: str, max_hops: int = 6
    ) -> list[list[Any]]:
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")
        result = self.client.read(
            f"""
            MATCH p=(start {{id:$start_id}})-[*1..{int(max_hops)}]-(end {{id:$end_id}})
            RETURN nodes(p), relationships(p)
            LIMIT 25
            """,
            {"start_id": start_id, "end_id": end_id},
        )
        return result.result_set

    def preceding(self, node_id: str, timestamp: str) -> list[list[Any]]:
        result = self.client.read(
            """
            MATCH (n {id:$node_id})-[r]-(m)
            WHERE m.timestamp IS NOT NULL AND m.timestamp < $timestamp
            RETURN m.id, labels(m), m.name, m.timestamp, type(r)
            ORDER BY m.timestamp DESC
            """,
            {"node_id": node_id, "timestamp": timestamp},
        )
        return result.result_set

    def relationship_evidence(self, source_id: str, target_id: str) -> list[list[Any]]:
        """Return relationship properties and the source IDs recorded on each edge."""
        result = self.client.read(
            """
            MATCH (source {id:$source_id})-[r]-(target {id:$target_id})
            RETURN type(r), properties(r), coalesce(r.evidence_source_ids, [])
            ORDER BY r.edge_id
            """,
            {"source_id": source_id, "target_id": target_id},
        )
        return result.result_set
