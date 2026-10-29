from datetime import UTC, datetime
from typing import Any

from continuum.core import GraphEdge, GraphNode, Ontology, World
from continuum.graph.loader import WorldLoader


class FakeResult:
    def __init__(self, result_set: list[list[Any]] | None = None):
        self.result_set = result_set or []


class FakeClient:
    def __init__(self):
        self.queries: list[tuple[str, dict[str, Any] | None]] = []

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> FakeResult:
        self.queries.append((cypher, params))
        return FakeResult()

    def reset(self) -> None:
        self.queries.append(("RESET", None))


class Data:
    def nodes(self):
        return (
            GraphNode("a", "Entity", "A", properties={"kind": "entity"}),
            GraphNode("b", "Outcome", "B"),
            GraphNode(
                "source-1",
                "Source",
                "Source 1",
                properties={
                    "record": "record-1",
                    "span": "line 1",
                    "status": "OBSERVED",
                },
                observed_at=datetime(2026, 8, 1, 9, tzinfo=UTC),
            ),
        )

    def edges(self):
        return (
            GraphEdge(
                "a",
                "AFFECTS",
                "b",
                evidence_source_ids=("source-1",),
            ),
        )


def test_world_loader_is_generic() -> None:
    world = World("test", Ontology("test"), Data())
    client = FakeClient()

    WorldLoader(client).load(world, reset=True)

    queries = [query for query, _ in client.queries]
    cypher = "\n".join(queries)

    assert queries[0] == "RESET"
    assert "MERGE (n:Entity {id: $id})" in cypher
    assert "MERGE (n:Outcome {id: $id})" in cypher
    assert "MERGE (source)-[r:AFFECTS {edge_id: $edge_id}]->(target)" in cypher


def test_loader_uses_stable_node_id_for_merge() -> None:
    world = World("test", Ontology("test"), Data())
    client = FakeClient()

    WorldLoader(client).load(world)

    node_queries = [
        (query, params) for query, params in client.queries if "MERGE (n:" in query
    ]

    assert node_queries
    for query, params in node_queries:
        assert "{id: $id}" in query
        assert params is not None
        assert "id" in params
        assert "properties" in params
        assert params["id"] in {"a", "b", "source-1"}
        assert params["properties"]["name"] in {"A", "B", "Source 1"}
        assert params["properties"].get("id") is None


def test_loader_does_not_allow_properties_to_override_node_identity() -> None:
    class DataWithReservedProperty:
        def nodes(self):
            return (
                GraphNode(
                    "a",
                    "Entity",
                    "A",
                    properties={"id": "wrong-id", "kind": "entity"},
                ),
            )

        def edges(self):
            return ()

    client = FakeClient()
    WorldLoader(client).load(
        World("test", Ontology("test"), DataWithReservedProperty())
    )

    node_params = next(
        params for query, params in client.queries if "MERGE (n:Entity" in query
    )
    assert node_params["id"] == "a"
    assert node_params["properties"]["name"] == "A"
    assert "id" not in node_params["properties"]


def test_loader_preserves_temporal_and_edge_provenance_properties() -> None:
    timestamp = datetime(2026, 8, 1, 9, tzinfo=UTC)
    data = type(
        "TemporalData",
        (),
        {
            "nodes": lambda self: (
                GraphNode("a", "Entity", "A", timestamp=timestamp),
                GraphNode("b", "Outcome", "B"),
                GraphNode(
                    "source-1",
                    "Source",
                    "Source 1",
                    properties={
                        "record": "record-1",
                        "span": "line 1",
                        "status": "OBSERVED",
                    },
                    observed_at=timestamp,
                ),
            ),
            "edges": lambda self: (
                GraphEdge(
                    "a",
                    "AFFECTS",
                    "b",
                    timestamp=timestamp,
                    evidence_source_ids=("source-1",),
                ),
            ),
        },
    )()

    client = FakeClient()
    WorldLoader(client).load(World("test", Ontology("test"), data))

    node_params = next(
        params for query, params in client.queries if "MERGE (n:Entity" in query
    )
    edge_params = next(
        params
        for query, params in client.queries
        if "MERGE (source)-[r:AFFECTS" in query
    )

    assert node_params["properties"]["timestamp"] == "2026-08-01T09:00:00Z"
    assert edge_params["properties"]["timestamp"] == "2026-08-01T09:00:00Z"
    assert edge_params["properties"]["evidence_source_ids"] == ["source-1"]
    assert edge_params["properties"]["evidence_status"] == "OBSERVED"
    assert edge_params["properties"]["provenance_version"] == 1
    assert edge_params["edge_id"].startswith("edge-")
