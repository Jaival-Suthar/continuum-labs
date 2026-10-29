from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from continuum.graph import GraphClient, WorldLoader
from domains.software.world import SOFTWARE_WORLD

EXPECTED_PRIMARY_PATH = [
    "commit-001",
    "dependency-gateway-sdk",
    "service-payments",
    "deployment-001",
    "metric-001",
    "incident-001",
]

EXPECTED_PRIMARY_RELATIONSHIPS = [
    "CHANGED",
    "DEPENDS_ON",
    "AFFECTS",
    "AFFECTS",
    "RESULTED_IN",
]


def fail(message: str) -> None:
    raise AssertionError(message)


def query_rows(client: GraphClient, cypher: str, params: dict | None = None):
    return client.read(cypher, params).result_set


def check_world_shape(client: GraphClient) -> None:
    rows = query_rows(
        client,
        """
        MATCH (n)
        RETURN count(n), collect(labels(n))
        """,
    )
    node_count, label_sets = rows[0]
    labels = {label for label_set in label_sets for label in label_set}

    if node_count < 15:
        fail(f"software world too small: {node_count} nodes")
    if len(labels) < 8:
        fail(f"software world lacks domain variety: {len(labels)} labels")


def check_primary_path(client: GraphClient) -> None:
    rows = query_rows(
        client,
        """
        MATCH p=(commit {id:$start})-[:CHANGED]->(dependency)
          -[:DEPENDS_ON]->(service)
          -[:AFFECTS]->(deployment)
          -[:AFFECTS]->(metric)
          -[:RESULTED_IN]->(incident {id:$end})
        RETURN [n IN nodes(p) | n.id],
               [r IN relationships(p) | type(r)]
        """,
        {"start": "commit-001", "end": "incident-001"},
    )

    if not rows:
        fail("ground-truth six-node investigation path not found")

    node_ids, relationships = rows[0]
    if node_ids != EXPECTED_PRIMARY_PATH:
        fail(f"unexpected primary path: {node_ids}")
    if relationships != EXPECTED_PRIMARY_RELATIONSHIPS:
        fail(f"unexpected primary relationships: {relationships}")


def check_multiple_hypotheses(client: GraphClient) -> None:
    rows = query_rows(
        client,
        """
        MATCH (candidate)-[:AFFECTS]->(metric {id:'metric-001'})
        RETURN candidate.id, candidate.timestamp, candidate.hypothesis
        ORDER BY candidate.id
        """,
    )

    candidate_ids = {row[0] for row in rows}
    required = {"deployment-001", "infra-event-001", "config-001"}
    if not required <= candidate_ids:
        fail(
            "software world does not contain the required competing "
            f"explanations: missing {sorted(required - candidate_ids)}"
        )


def check_temporal_trap(client: GraphClient) -> None:
    rows = query_rows(
        client,
        """
        MATCH (config {id:'config-001'})-[r:AFFECTS]->(metric {id:'metric-001'})
        MATCH (metric)-[:RESULTED_IN]->(incident {id:'incident-001'})
        RETURN config.timestamp, metric.timestamp, incident.timestamp, r.timestamp
        """,
    )

    if not rows:
        fail("configuration temporal-trap relationship not found")

    config_ts, _metric_ts, incident_ts, edge_ts = rows[0]
    if not (config_ts > incident_ts and edge_ts > incident_ts):
        fail(
            "configuration alternative is not temporally after the incident "
            "as required by the M3 scenario"
        )


def check_distractors(client: GraphClient) -> None:
    rows = query_rows(
        client,
        """
        MATCH p=(commit {id:'commit-002'})-[:CHANGED]->(dependency)
          -[:DEPENDS_ON]->(service)
          -[:AFFECTS]->(deployment)
          -[:AFFECTS]->(metric)
        RETURN [n IN nodes(p) | n.id]
        """,
    )

    if not rows:
        fail("unrelated distractor chain is missing")


def check_missing_evidence(client: GraphClient) -> None:
    rows = query_rows(
        client,
        """
        MATCH (candidate)-[r:AFFECTS]->(metric {id:'metric-001'})
        WHERE candidate.id IN ['infra-event-001', 'config-001']
        RETURN candidate.id,
               coalesce(r.evidence_source_ids, [])
        ORDER BY candidate.id
        """,
    )

    evidence = {row[0]: row[1] for row in rows}
    if evidence.get("infra-event-001") not in ([], None):
        fail("infrastructure alternative unexpectedly has evidence")
    if evidence.get("config-001") not in ([], None):
        fail("configuration alternative unexpectedly has evidence")


def main() -> int:
    print("M3 software world check")

    client = GraphClient()

    try:
        WorldLoader(client).load(SOFTWARE_WORLD, reset=True)

        check_world_shape(client)
        check_primary_path(client)
        check_multiple_hypotheses(client)
        check_temporal_trap(client)
        check_distractors(client)
        check_missing_evidence(client)

    except (AssertionError, ValueError, TypeError) as exc:
        print(f"FAIL: {exc}")
        return 1

    print("software_world=PASS")
    print("ground_truth_multi_hop_path=PASS hops=5")
    print("multiple_hypotheses=PASS")
    print("temporal_conflict=PASS")
    print("distractors=PASS")
    print("missing_evidence=PASS")
    print("M3_STATUS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
