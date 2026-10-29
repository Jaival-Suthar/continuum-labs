from falkordb.edge import Edge
from falkordb.node import Node

from continuum.temporal import TEMPORAL_INVALID, TemporalQueries


class Result:
    def __init__(self, result_set):
        self.result_set = result_set


class FakeClient:
    def __init__(self):
        self.calls = []

    def read(self, cypher, params=None):
        self.calls.append((cypher, params))
        if "RETURN n.timestamp" in cypher:
            return Result([["2026-08-01T10:00:00Z"]])
        if "RETURN nodes(p), relationships(p)" in cypher:
            nodes = [
                Node(properties={"id": "cause", "timestamp": "2026-08-01T11:00:00Z"}),
                Node(properties={"id": "effect", "timestamp": "2026-08-01T10:00:00Z"}),
            ]
            edges = [
                Edge(
                    0,
                    "AFFECTS",
                    1,
                    edge_id="edge-1",
                    properties={"timestamp": "2026-08-01T11:00:00Z"},
                )
            ]
            return Result([[nodes, edges]])
        if "n.valid_from" in cypher:
            return Result(
                [
                    [
                        "config-B",
                        ["Configuration"],
                        "payments timeout configuration B",
                        "2026-08-01T09:10:00Z",
                        "2026-08-01T10:00:00Z",
                        None,
                        None,
                    ]
                ]
            )
        return Result([])


def test_temporal_query_converts_falkordb_path_objects():
    client = FakeClient()
    results = TemporalQueries(client).filter_temporal_paths(
        TemporalQueries(client).paths_between("cause", "effect")
    )

    assert len(results) == 1
    assert results[0].path.node_ids == ("cause", "effect")
    assert results[0].path.relationships == ("AFFECTS",)
    assert results[0].check.status == TEMPORAL_INVALID


def test_temporal_state_query_returns_graph_state():
    rows = TemporalQueries(FakeClient()).state_at(
        "2026-08-01T09:20:00Z",
        label="Configuration",
    )
    assert rows[0][0] == "config-B"


def test_ordering_query_uses_anchor_event_time():
    client = FakeClient()
    # The fake has no candidate rows; the important contract here is that the
    # anchor timestamp is resolved and embedded as the canonical UTC parameter.
    rows = TemporalQueries(client).ordering(
        "incident-001",
        before_timestamp="2026-08-01T10:00:00Z",
    )
    assert rows == []
    assert any(
        "candidate.timestamp < $before_timestamp" in query for query, _ in client.calls
    )
