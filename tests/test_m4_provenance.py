from datetime import UTC, datetime

import pytest

from continuum.core import (
    Evidence,
    EvidenceStatus,
    GraphEdge,
    GraphNode,
    Ontology,
    World,
)
from continuum.graph.loader import WorldLoader
from continuum.graph.provenance import relationship_with_evidence


def test_graph_edge_has_deterministic_stable_identity() -> None:
    timestamp = datetime(2026, 8, 1, 9, tzinfo=UTC)
    first = GraphEdge(
        "a",
        "AFFECTS",
        "b",
        timestamp=timestamp,
        evidence_source_ids=("source-1",),
        properties={"role": "primary"},
    )
    second = GraphEdge(
        "a",
        "AFFECTS",
        "b",
        timestamp=timestamp,
        evidence_source_ids=("source-1",),
        properties={"role": "primary"},
    )

    assert first.stable_id == second.stable_id
    assert first.stable_id.startswith("edge-")

    metadata_change = GraphEdge(
        "a",
        "AFFECTS",
        "b",
        timestamp=timestamp,
        evidence_source_ids=("source-1",),
        properties={"role": "metadata-changed"},
    )
    assert metadata_change.stable_id == first.stable_id


def test_graph_edge_explicit_ids_allow_multiple_relationship_occurrences() -> None:
    first = GraphEdge("a", "AFFECTS", "b", edge_id="edge-1")
    second = GraphEdge("a", "AFFECTS", "b", edge_id="edge-2")

    assert first.stable_id == "edge-1"
    assert second.stable_id == "edge-2"
    assert first.stable_id != second.stable_id


def test_graph_edge_rejects_invalid_evidence_status() -> None:
    with pytest.raises(ValueError, match="Unsupported evidence status"):
        GraphEdge(
            "a",
            "AFFECTS",
            "b",
            properties={"evidence_status": "MADE_UP"},
        )


def test_world_validates_evidence_source_references() -> None:
    class Data:
        def nodes(self):
            return (
                GraphNode("a", "Entity", "A"),
                GraphNode("b", "Outcome", "B"),
                GraphNode(
                    "source-1",
                    "Source",
                    "source",
                    properties={
                        "status": "OBSERVED",
                        "record": "record-1",
                        "span": "line 10",
                    },
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

    World("test", Ontology("test"), Data()).validate()


def test_world_rejects_unknown_evidence_source() -> None:
    class Data:
        def nodes(self):
            return (
                GraphNode("a", "Entity", "A"),
                GraphNode("b", "Outcome", "B"),
            )

        def edges(self):
            return (
                GraphEdge(
                    "a",
                    "AFFECTS",
                    "b",
                    evidence_source_ids=("missing-source",),
                ),
            )

    with pytest.raises(ValueError, match="Unknown evidence source ids"):
        World("test", Ontology("test"), Data()).validate()


def test_evidence_model_requires_canonical_status() -> None:
    evidence = Evidence(
        id="source-1",
        source_id="source-1",
        status=EvidenceStatus.OBSERVED,
        observed_at=datetime(2026, 8, 1, 9, tzinfo=UTC),
        record="record-1",
        span="line 10",
    )

    assert evidence.status == "OBSERVED"
    assert evidence.record == "record-1"
    assert evidence.span == "line 10"


class FakeResult:
    def __init__(self, result_set):
        self.result_set = result_set


class FakeClient:
    def __init__(self):
        self.calls = []

    def read(self, cypher, params=None):
        self.calls.append((cypher, params))
        return FakeResult(
            [
                [
                    "a",
                    "AFFECTS",
                    "b",
                    "edge-1",
                    "2026-08-01T09:00:00Z",
                    None,
                    None,
                    "OBSERVED",
                    ["source-1"],
                    ["OBSERVED"],
                    ["2026-08-01T09:00:00Z"],
                    ["record-1"],
                    ["line 10"],
                    ["source record"],
                ]
            ]
        )


def test_relationship_provenance_resolves_auditable_source_fields() -> None:
    relationships = relationship_with_evidence(FakeClient(), "a", "b")

    assert len(relationships) == 1
    relationship = relationships[0]

    assert relationship.edge_id == "edge-1"
    assert relationship.evidence_status == "OBSERVED"
    assert relationship.evidence_source_ids == ("source-1",)
    assert len(relationship.evidence) == 1
    evidence = relationship.evidence[0]
    assert evidence.source_id == "source-1"
    assert evidence.record == "record-1"
    assert evidence.span == "line 10"
    assert evidence.status == "OBSERVED"


def test_loader_keys_relationship_merge_by_edge_id_for_repeated_endpoints() -> None:
    class Data:
        def nodes(self):
            return (
                GraphNode("a", "Entity", "A"),
                GraphNode("b", "Outcome", "B"),
            )

        def edges(self):
            return (
                GraphEdge(
                    "a",
                    "AFFECTS",
                    "b",
                    timestamp=datetime(2026, 8, 1, 9, tzinfo=UTC),
                    edge_id="edge-occurrence-1",
                ),
                GraphEdge(
                    "a",
                    "AFFECTS",
                    "b",
                    timestamp=datetime(2026, 8, 1, 10, tzinfo=UTC),
                    edge_id="edge-occurrence-2",
                ),
            )

    class FakeClient:
        def __init__(self):
            self.calls = []

        def query(self, cypher, params=None):
            self.calls.append((cypher, params))

            class Result:
                def __init__(self):
                    self.result_set = []

            return Result()

        def reset(self):
            pass

    client = FakeClient()
    WorldLoader(client).load(World("test", Ontology("test"), Data()))

    edge_calls = [
        params for query, params in client.calls if "MERGE (source)-[r:AFFECTS" in query
    ]

    assert [params["edge_id"] for params in edge_calls] == [
        "edge-occurrence-1",
        "edge-occurrence-2",
    ]
