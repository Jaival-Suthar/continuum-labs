from continuum.core import Evidence, EvidenceStatus, InvestigationPath
from continuum.investigator import Investigator


class Result:
    def __init__(self, result_set):
        self.result_set = result_set


class FakeGraph:
    def __init__(self):
        self.calls = []

    def read(self, cypher, params=None):
        self.calls.append((cypher, params))
        if (
            "MATCH (n {id:$node_id}) RETURN labels(n), n.id, n.name, n.timestamp"
            in cypher
        ):
            return Result(
                [[["Incident"], "incident-001", "INC-001", "2026-08-01T10:00:00Z"]]
            )
        if "RETURN properties(n)" in cypher:
            return Result(
                [[{"id": "incident-001", "timestamp": "2026-08-01T10:00:00Z"}]]
            )
        if (
            "MATCH (n {id:$node_id})-[r]-(m)" in cypher
            and "RETURN n.id, type(r)" not in cypher
        ):
            return Result(
                [
                    [
                        ["Metric"],
                        "metric-001",
                        "latency",
                        "2026-08-01T09:45:00Z",
                        None,
                        None,
                        None,
                        {"id": "metric-001"},
                    ]
                ]
            )
        if "RETURN labels(m), m.id" in cypher:
            return Result(
                [
                    [
                        ["Metric"],
                        "metric-001",
                        "latency",
                        "2026-08-01T09:45:00Z",
                        None,
                        None,
                        None,
                        {"id": "metric-001"},
                    ]
                ]
            )
        return Result([])


def test_rank_paths_is_deterministic_and_transparent():
    investigator = Investigator(FakeGraph())
    strong = InvestigationPath(
        node_ids=("commit", "service", "incident"),
        relationships=("CHANGED", "RESULTED_IN"),
        edge_ids=("e1", "e2"),
        temporal_status="VALID",
        temporal_reason="path temporally consistent",
        evidence=(Evidence("s1", "s1", EvidenceStatus.OBSERVED),),
        supporting_relationship_count=2,
        missing_evidence_count=0,
    )
    weak = InvestigationPath(
        node_ids=("infra", "metric", "incident"),
        relationships=("AFFECTS", "RESULTED_IN"),
        edge_ids=("e3", "e4"),
        temporal_status="VALID",
        temporal_reason="path temporally consistent",
        evidence=(),
        supporting_relationship_count=0,
        missing_evidence_count=2,
    )
    ranked = investigator.rank_paths([weak, strong])
    assert ranked[0].path == strong
    assert ranked[0].rank_key > ranked[1].rank_key
    assert ranked[0].temporal_validity == 2


def test_conflicting_evidence_surfaces_invalid_temporal_path():
    investigator = Investigator(FakeGraph())
    invalid = InvestigationPath(
        node_ids=("config", "metric", "incident"),
        relationships=("AFFECTS", "RESULTED_IN"),
        edge_ids=("e1", "e2"),
        temporal_status="INVALID",
        temporal_reason="event occurs after a later event in path",
    )
    conflicts = investigator.find_conflicting_evidence([invalid])
    assert len(conflicts) == 1
    assert "rejected" in conflicts[0]


def test_find_outcome_uses_falkordb_exact_node_lookup():
    graph = FakeGraph()
    investigator = Investigator(graph)
    outcome = investigator.find_outcome("Why did incident-001 happen?")
    assert outcome.id == "incident-001"
    assert any("MATCH (n {id:$node_id})" in query for query, _ in graph.calls)
