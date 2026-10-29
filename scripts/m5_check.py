from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from continuum.cli.output import CheckResult, checks, failure, header, success
from continuum.graph import GraphClient, WorldLoader
from continuum.temporal import (
    TEMPORAL_INVALID,
    TEMPORAL_UNKNOWN,
    TEMPORAL_VALID,
    TemporalQueries,
    after,
    before,
    between,
    preceded_by,
    valid_at,
)
from domains.software.world import SOFTWARE_WORLD

PRIMARY_PATH = (
    "commit-001",
    "dependency-gateway-sdk",
    "service-payments",
    "deployment-001",
    "metric-001",
    "incident-001",
)


def fail(message: str) -> None:
    raise AssertionError(message)


def check_temporal_metadata() -> None:
    nodes = {node.id: node for node in SOFTWARE_WORLD.data.nodes()}

    for node_id in PRIMARY_PATH:
        if node_id in {"dependency-gateway-sdk", "service-payments"}:
            continue
        if nodes[node_id].timestamp is None:
            fail(f"{node_id} is missing timestamp")

    edges = {
        (edge.source_id, edge.target_id): edge for edge in SOFTWARE_WORLD.data.edges()
    }
    for pair in [
        ("commit-001", "dependency-gateway-sdk"),
        ("dependency-gateway-sdk", "service-payments"),
        ("service-payments", "deployment-001"),
        ("deployment-001", "metric-001"),
        ("metric-001", "incident-001"),
        ("config-001", "metric-001"),
    ]:
        if edges[pair].timestamp is None:
            fail(f"edge {pair[0]} -> {pair[1]} is missing timestamp")

    states = [nodes["config-A"], nodes["config-B"]]
    if any(state.valid_from is None for state in states):
        fail("configuration state is missing valid_from")
    if any(state.valid_until is None for state in states):
        fail("configuration state is missing valid_until")


def check_predicates() -> None:
    nodes = {node.id: node for node in SOFTWARE_WORLD.data.nodes()}
    commit = nodes["commit-001"]
    deployment = nodes["deployment-001"]
    incident = nodes["incident-001"]

    if before(commit.timestamp, incident.timestamp) is not True:
        fail("before(commit-001, incident-001) is not True")
    if after(incident.timestamp, commit.timestamp) is not True:
        fail("after(incident-001, commit-001) is not True")
    if between(deployment.timestamp, commit.timestamp, incident.timestamp) is not True:
        fail("between(deployment-001, commit-001, incident-001) is not True")
    if preceded_by(deployment.timestamp, incident.timestamp) is not True:
        fail("preceded_by(deployment-001, incident-001) is not True")

    if before(None, incident.timestamp) is not None:
        fail("missing temporal metadata must be UNKNOWN")


def check_state_at(temporal: TemporalQueries) -> str:
    rows = temporal.state_at("2026-08-01T09:20:00Z", label="Configuration")
    if [row[0] for row in rows] != ["config-B"]:
        fail(f"unexpected configuration state at 09:20: {[row[0] for row in rows]}")

    config_b = next(
        node for node in SOFTWARE_WORLD.data.nodes() if node.id == "config-B"
    )
    if valid_at(config_b, "2026-08-01T09:20:00Z") is not True:
        fail("valid_at(config-B, 09:20) is not True")
    if valid_at(config_b, "2026-08-01T10:01:00Z") is not False:
        fail("valid_at(config-B, 10:01) is not False")
    return rows[0][0]


def check_ordering(temporal: TemporalQueries) -> int:
    rows = temporal.ordering(
        "incident-001",
        before_timestamp="2026-08-01T10:00:00Z",
    )
    if not rows:
        fail("ordering query returned no preceding events")

    timestamps = [row[3] for row in rows]
    if timestamps != sorted(timestamps):
        fail("ordering query is not sorted by event timestamp")

    ids = {row[0] for row in rows}
    required = {"commit-001", "deployment-001", "metric-001"}
    if not required <= ids:
        fail(f"ordering query is missing required events: {sorted(required - ids)}")
    if "config-001" in ids:
        fail("configuration temporal trap incorrectly appeared before incident")
    return len(rows)


def check_temporal_paths(temporal: TemporalQueries) -> tuple[str, str]:
    valid_results = temporal.filter_temporal_paths(
        temporal.paths_between("commit-001", "incident-001", max_hops=5)
    )
    primary = [
        result for result in valid_results if result.path.node_ids == PRIMARY_PATH
    ]
    if len(primary) != 1:
        fail("ground-truth primary path was not discovered exactly once")
    if primary[0].check.status != TEMPORAL_VALID:
        fail(f"primary path status was {primary[0].check.status}")

    invalid_results = temporal.filter_temporal_paths(
        temporal.paths_between("config-001", "incident-001", max_hops=2)
    )
    trap = [
        result
        for result in invalid_results
        if result.path.node_ids == ("config-001", "metric-001", "incident-001")
    ]
    if len(trap) != 1:
        fail("configuration temporal-trap path was not discovered exactly once")
    if trap[0].check.status != TEMPORAL_INVALID:
        fail(f"temporal trap status was {trap[0].check.status}")
    if trap[0].check.reason != "event occurs after a later event in path":
        fail(f"unexpected temporal trap reason: {trap[0].check.reason}")

    unknown = temporal.filter_temporal_paths(
        [
            type(primary[0].path)(
                node_ids=("unknown-a", "unknown-b"),
                relationships=("AFFECTS",),
                node_timestamps=(None, None),
                edge_timestamps=(None,),
                node_records=({"id": "unknown-a"}, {"id": "unknown-b"}),
                edge_records=({"edge_id": "unknown-edge"},),
            )
        ]
    )[0]
    if unknown.check.status != TEMPORAL_UNKNOWN:
        fail("path with no temporal metadata must be UNKNOWN")

    return primary[0].check.status, trap[0].check.status


def check_observation_time() -> None:
    nodes = {node.id: node for node in SOFTWARE_WORLD.data.nodes()}
    event = nodes["commit-001"]
    source = nodes["source-commit-001"]

    if event.timestamp.isoformat().replace("+00:00", "Z") != "2026-08-01T09:00:00Z":
        fail("commit event timestamp changed unexpectedly")
    if source.observed_at.isoformat().replace("+00:00", "Z") != "2026-08-01T09:05:00Z":
        fail("source observed_at timestamp is not distinct from event time")
    if before(event.timestamp, nodes["incident-001"].timestamp) is not True:
        fail("event ordering incorrectly uses observed_at instead of timestamp")


def main() -> int:
    header("M5", "Temporal investigation")

    client = GraphClient()
    temporal = TemporalQueries(client)

    try:
        SOFTWARE_WORLD.validate()
        WorldLoader(client).load(SOFTWARE_WORLD, reset=True)

        check_temporal_metadata()
        check_predicates()
        state_id = check_state_at(temporal)
        ordering_count = check_ordering(temporal)
        valid_status, invalid_status = check_temporal_paths(temporal)
        check_observation_time()

    except (AssertionError, ValueError, TypeError) as exc:
        failure(str(exc))
        return 1

    checks(
        [
            CheckResult("Temporal metadata", "PASS"),
            CheckResult(
                "Ordering queries",
                f"PASS · preceding_events={ordering_count}",
            ),
            CheckResult("Ordering predicates", "PASS"),
            CheckResult("State-at-time", f"PASS · 09:20={state_id}"),
            CheckResult("Valid temporal path", f"PASS · {valid_status}"),
            CheckResult(
                "Cause-after-effect rejection",
                f"PASS · {invalid_status}",
            ),
            CheckResult("Event time ≠ observation time", "PASS"),
            CheckResult("Missing time", f"PASS · {TEMPORAL_UNKNOWN}"),
        ]
    )

    success("M5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
