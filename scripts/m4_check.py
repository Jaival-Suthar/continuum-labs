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
from continuum.core import EvidenceStatus
from continuum.graph import GraphClient, WorldLoader
from continuum.graph.provenance import relationship_with_evidence
from domains.software.world import SOFTWARE_WORLD

PRIMARY_EDGES = [
    ("commit-001", "dependency-gateway-sdk"),
    ("dependency-gateway-sdk", "service-payments"),
    ("service-payments", "deployment-001"),
    ("deployment-001", "metric-001"),
    ("metric-001", "incident-001"),
]


def fail(message: str) -> None:
    raise AssertionError(message)


def query_rows(client: GraphClient, cypher: str, params: dict | None = None):
    return client.read(cypher, params).result_set


def check_edge_identity(client: GraphClient) -> int:
    rows = query_rows(
        client,
        """
        MATCH ()-[r]->()
        RETURN r.edge_id, type(r), r.evidence_status
        ORDER BY r.edge_id
        """,
    )

    if not rows:
        fail("graph contains no relationships")

    edge_ids = [row[0] for row in rows]
    if any(not edge_id for edge_id in edge_ids):
        fail("one or more relationships is missing stable edge_id")
    if len(edge_ids) != len(set(edge_ids)):
        fail("relationship edge_id values are not unique")

    invalid_statuses = {row[2] for row in rows if row[2] not in EvidenceStatus.ALL}
    if invalid_statuses:
        fail(f"invalid evidence statuses: {sorted(invalid_statuses)}")

    return len(rows)


def check_source_records(client: GraphClient) -> int:
    rows = query_rows(
        client,
        """
        MATCH (s:Source)
        RETURN s.id, s.name, s.record, s.span, s.observed_at, s.status
        ORDER BY s.id
        """,
    )

    if not rows:
        fail("no Source nodes found")

    for source_id, name, record, span, observed_at, status in rows:
        if not name:
            fail(f"source {source_id} has no name")
        if not record:
            fail(f"source {source_id} has no record")
        if not span:
            fail(f"source {source_id} has no source span")
        if not observed_at:
            fail(f"source {source_id} has no observed_at timestamp")
        if status not in EvidenceStatus.ALL:
            fail(f"source {source_id} has invalid status {status}")

    return len(rows)


def check_primary_provenance(client: GraphClient) -> None:
    for source_id, target_id in PRIMARY_EDGES:
        relationships = relationship_with_evidence(client, source_id, target_id)
        matching = [
            relationship
            for relationship in relationships
            if relationship.source_id == source_id
            and relationship.target_id == target_id
        ]
        if not matching:
            fail(f"missing relationship {source_id} -> {target_id}")

        relationship = matching[0]
        if not relationship.edge_id:
            fail(f"{source_id} -> {target_id} has no edge_id")
        if relationship.evidence_status != EvidenceStatus.OBSERVED:
            fail(
                f"{source_id} -> {target_id} has unexpected evidence status "
                f"{relationship.evidence_status}"
            )
        if not relationship.evidence:
            fail(f"{source_id} -> {target_id} has no resolved evidence")

        for evidence in relationship.evidence:
            if not evidence.record or not evidence.span:
                fail(
                    f"{source_id} -> {target_id} evidence {evidence.id} "
                    "is missing record/span"
                )
            if evidence.observed_at is None:
                fail(
                    f"{source_id} -> {target_id} evidence {evidence.id} "
                    "is missing observed_at"
                )
            if evidence.status not in EvidenceStatus.ALL:
                fail(
                    f"{source_id} -> {target_id} evidence {evidence.id} "
                    f"has invalid status {evidence.status}"
                )


def check_missing_evidence_is_explicit(client: GraphClient) -> None:
    rows = query_rows(
        client,
        """
        MATCH (candidate)-[r:AFFECTS]->(metric {id:'metric-001'})
        WHERE candidate.id IN ['infra-event-001', 'config-001']
        RETURN candidate.id,
               r.edge_id,
               coalesce(r.evidence_status, 'UNKNOWN'),
               coalesce(r.evidence_source_ids, [])
        ORDER BY candidate.id
        """,
    )

    if len(rows) != 2:
        fail("expected both competing hypotheses")

    for candidate_id, edge_id, status, evidence_source_ids in rows:
        if not edge_id:
            fail(f"{candidate_id} relationship has no edge_id")
        if status != EvidenceStatus.UNKNOWN:
            fail(
                f"{candidate_id} should remain UNKNOWN without source evidence; "
                f"got {status}"
            )
        if evidence_source_ids not in ([], None):
            fail(
                f"{candidate_id} unexpectedly has evidence sources: "
                f"{evidence_source_ids}"
            )


def main() -> int:
    header("M4", "Provenance verification")

    client = GraphClient()

    try:
        WorldLoader(client).load(SOFTWARE_WORLD, reset=True)

        edge_count = check_edge_identity(client)
        source_count = check_source_records(client)
        check_primary_provenance(client)
        check_missing_evidence_is_explicit(client)

    except (AssertionError, ValueError, TypeError) as exc:
        failure(str(exc))
        return 1

    checks(
        [
            CheckResult(
                "Relationship identity",
                f"PASS · edges={edge_count}",
            ),
            CheckResult(
                "Source records",
                f"PASS · sources={source_count}",
            ),
            CheckResult(
                "Primary path provenance",
                "PASS",
            ),
            CheckResult(
                "Missing evidence explicit",
                "PASS",
            ),
        ]
    )

    success("M4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
