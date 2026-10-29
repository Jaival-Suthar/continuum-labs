import pytest

from continuum.graph import GraphClient, WorldLoader
from continuum.temporal import TEMPORAL_INVALID, TEMPORAL_VALID, TemporalQueries


@pytest.fixture
def temporal_graph():
    from domains.software.world import SOFTWARE_WORLD

    client = GraphClient()
    WorldLoader(client).load(SOFTWARE_WORLD, reset=True)
    return client


@pytest.mark.integration
def test_ordering_query_returns_events_before_incident(temporal_graph):
    rows = TemporalQueries(temporal_graph).ordering(
        "incident-001",
        before_timestamp="2026-08-01T10:00:00Z",
    )

    ids = [row[0] for row in rows]
    assert ids == sorted(
        ids, key=lambda node_id: next(row[3] for row in rows if row[0] == node_id)
    )
    assert "commit-001" in ids
    assert "deployment-001" in ids
    assert "metric-001" in ids
    assert "config-001" not in ids


@pytest.mark.integration
def test_state_at_returns_configuration_active_at_0920(temporal_graph):
    rows = TemporalQueries(temporal_graph).state_at(
        "2026-08-01T09:20:00Z",
        label="Configuration",
    )

    assert [row[0] for row in rows] == ["config-B"]
    assert rows[0][3] == "2026-08-01T09:10:00Z"
    assert rows[0][4] == "2026-08-01T10:00:00Z"


@pytest.mark.integration
def test_primary_path_is_temporally_valid(temporal_graph):
    results = TemporalQueries(temporal_graph).filter_temporal_paths(
        TemporalQueries(temporal_graph).paths_between(
            "commit-001",
            "incident-001",
            max_hops=5,
        )
    )

    primary = [
        result
        for result in results
        if result.path.node_ids
        == (
            "commit-001",
            "dependency-gateway-sdk",
            "service-payments",
            "deployment-001",
            "metric-001",
            "incident-001",
        )
    ]

    assert len(primary) == 1
    assert primary[0].check.status == TEMPORAL_VALID
    assert primary[0].check.valid is True


@pytest.mark.integration
def test_configuration_temporal_trap_is_rejected(temporal_graph):
    temporal = TemporalQueries(temporal_graph)
    results = temporal.filter_temporal_paths(
        temporal.paths_between("config-001", "incident-001", max_hops=2)
    )

    matching = [
        result
        for result in results
        if result.path.node_ids == ("config-001", "metric-001", "incident-001")
    ]

    assert len(matching) == 1
    assert matching[0].check.status == TEMPORAL_INVALID
    assert matching[0].check.valid is False
    assert matching[0].check.reason == "event occurs after a later event in path"


@pytest.mark.integration
def test_missing_intermediate_time_is_not_automatically_invalid(temporal_graph):
    temporal = TemporalQueries(temporal_graph)
    results = temporal.filter_temporal_paths(
        temporal.paths_between(
            "commit-001",
            "incident-001",
            max_hops=5,
        )
    )

    primary = next(
        result
        for result in results
        if result.path.node_ids
        == (
            "commit-001",
            "dependency-gateway-sdk",
            "service-payments",
            "deployment-001",
            "metric-001",
            "incident-001",
        )
    )
    assert primary.check.valid is True


@pytest.mark.integration
def test_event_timestamp_and_source_observed_at_are_distinct(temporal_graph):
    row = temporal_graph.read(
        """
        MATCH (event {id:'commit-001'})
        MATCH (source:Source {id:'source-commit-001'})
        RETURN event.timestamp, source.observed_at
        """
    ).result_set[0]

    assert row[0] == "2026-08-01T09:00:00Z"
    assert row[1] == "2026-08-01T09:05:00Z"
