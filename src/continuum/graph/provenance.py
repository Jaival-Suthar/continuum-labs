from __future__ import annotations

from typing import Any

from continuum.core.models import Evidence, EvidenceStatus, GraphRelationship
from continuum.graph.client import GraphClient


def _evidence_from_row(
    evidence_ids: list[Any],
    evidence_statuses: list[Any],
    evidence_times: list[Any],
    evidence_records: list[Any],
    evidence_spans: list[Any],
    evidence_names: list[Any],
) -> tuple[Evidence, ...]:
    resolved: list[Evidence] = []
    for index, source_id in enumerate(evidence_ids):
        if not source_id:
            continue
        status = (
            evidence_statuses[index]
            if index < len(evidence_statuses) and evidence_statuses[index]
            else EvidenceStatus.UNKNOWN
        )
        observed_at = evidence_times[index] if index < len(evidence_times) else None
        record = evidence_records[index] if index < len(evidence_records) else None
        span = evidence_spans[index] if index < len(evidence_spans) else None
        name = evidence_names[index] if index < len(evidence_names) else None
        metadata = {"name": name} if name else {}
        resolved.append(
            Evidence(
                id=str(source_id),
                source_id=str(source_id),
                status=str(status),
                observed_at=observed_at,
                record=str(record) if record is not None else None,
                span=str(span) if span is not None else None,
                metadata=metadata,
            )
        )
    return tuple(resolved)


def relationship_with_evidence(
    client: GraphClient,
    source_id: str,
    target_id: str,
    edge_id: str | None = None,
) -> list[GraphRelationship]:
    """Return relationships between two nodes with inspectable source evidence.

    Evidence is resolved from the relationship's explicit
    ``evidence_source_ids`` property. This keeps provenance attached to the
    relationship rather than relying on an unrelated source-neighbor query.
    """

    edge_filter = "AND r.edge_id = $edge_id" if edge_id is not None else ""
    result = client.read(
        f"""
        MATCH (source {{id:$source_id}})-[r]-(target {{id:$target_id}})
        WHERE true {edge_filter}
        OPTIONAL MATCH (e:Source)
        WHERE e.id IN coalesce(r.evidence_source_ids, [])
        RETURN
            source.id,
            type(r),
            target.id,
            r.edge_id,
            r.timestamp,
            r.valid_from,
            r.valid_until,
            coalesce(r.evidence_status, 'UNKNOWN'),
            collect(e.id),
            collect(e.status),
            collect(e.observed_at),
            collect(e.record),
            collect(e.span),
            collect(e.name)
        ORDER BY r.edge_id
        """,
        {
            "source_id": source_id,
            "target_id": target_id,
            **({"edge_id": edge_id} if edge_id is not None else {}),
        },
    )

    relationships: list[GraphRelationship] = []
    for row in result.result_set:
        (
            rel_source,
            relationship,
            rel_target,
            persisted_edge_id,
            timestamp,
            valid_from,
            valid_until,
            evidence_status,
            evidence_ids,
            evidence_statuses,
            evidence_times,
            evidence_records,
            evidence_spans,
            evidence_names,
        ) = row

        evidence = _evidence_from_row(
            list(evidence_ids or []),
            list(evidence_statuses or []),
            list(evidence_times or []),
            list(evidence_records or []),
            list(evidence_spans or []),
            list(evidence_names or []),
        )

        relationships.append(
            GraphRelationship(
                source_id=rel_source,
                relationship=relationship,
                target_id=rel_target,
                evidence_source_ids=tuple(e.id for e in evidence),
                edge_id=persisted_edge_id,
                timestamp=timestamp,
                valid_from=valid_from,
                valid_until=valid_until,
                evidence_status=str(evidence_status),
                evidence=evidence,
            )
        )

    return relationships
