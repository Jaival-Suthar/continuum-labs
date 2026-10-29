from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from continuum.cli.output import (
    CheckResult,
    checks,
    failure,
    header,
    success,
)
from continuum.graph import GraphClient, GraphTraversal, initialize_graph
from continuum.graph.provenance import relationship_with_evidence
from continuum.graph.seed import seed_software_world


def fail(message: str) -> None:
    raise AssertionError(message)


def check_graph_connection(client: GraphClient) -> None:
    try:
        client.graph.query("RETURN 1 AS ok")
    except (ValueError, TypeError, RuntimeError) as exc:
        fail(f"FalkorDB connection failed: {exc}")


def check_connected_to_incident(
    traversal: GraphTraversal,
) -> int:
    connected = traversal.neighbors("incident-001")

    if not connected:
        fail("incident-001 has no connected records")

    return len(connected)


def check_commit_to_incident_paths(
    traversal: GraphTraversal,
) -> int:
    paths = traversal.paths_between(
        "commit-001",
        "incident-001",
    )

    if not paths:
        fail("No graph path connects commit-001 to incident-001")

    return len(paths)


def check_preceding_incident_records(
    traversal: GraphTraversal,
) -> int:
    preceding = traversal.preceding(
        "incident-001",
        "2026-08-01T10:00:00Z",
    )

    if not preceding:
        fail("No records were found preceding incident-001")

    return len(preceding)


def check_relationship_provenance(
    client: GraphClient,
) -> int:
    evidence = relationship_with_evidence(
        client,
        "commit-001",
        "dependency-gateway-sdk",
    )

    if not evidence:
        fail(
            "No provenance-bearing relationship found for "
            "commit-001 -> dependency-gateway-sdk"
        )

    return len(evidence)


def main() -> int:
    header("M1", "FalkorDB foundation verification")

    try:
        client = initialize_graph(GraphClient())

        check_graph_connection(client)

        seed_software_world(client)

        traversal = GraphTraversal(client)

        connected_count = check_connected_to_incident(traversal)
        path_count = check_commit_to_incident_paths(traversal)
        preceding_count = check_preceding_incident_records(traversal)
        provenance_count = check_relationship_provenance(client)

    except (
        AssertionError,
        ValueError,
        TypeError,
        RuntimeError,
    ) as exc:
        failure(str(exc))
        return 1

    checks(
        [
            CheckResult(
                "FalkorDB connection",
                "PASS",
            ),
            CheckResult(
                "Connected to incident",
                f"PASS · records={connected_count}",
            ),
            CheckResult(
                "Commit → incident paths",
                f"PASS · paths={path_count}",
            ),
            CheckResult(
                "Preceding incident records",
                f"PASS · records={preceding_count}",
            ),
            CheckResult(
                "Relationships with provenance",
                f"PASS · relationships={provenance_count}",
            ),
        ]
    )

    success("M1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
