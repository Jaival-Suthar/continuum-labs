from __future__ import annotations

from continuum.core.models import GraphRelationship
from continuum.graph.client import GraphClient


def relationship_with_evidence(
    client: GraphClient,
    source_id: str,
    target_id: str,
) -> list[GraphRelationship]:
    result = client.read(
        """
        MATCH (source {id:$source_id})-[r]-(target {id:$target_id})
        OPTIONAL MATCH (source)-[:SUPPORTED_BY]->(e:Source)
        RETURN source.id, type(r), target.id, collect(e.id)
        """,
        {"source_id": source_id, "target_id": target_id},
    )
    return [
        GraphRelationship(
            source_id=row[0],
            relationship=row[1],
            target_id=row[2],
            evidence_source_ids=tuple(sorted(x for x in row[3] if x)),
        )
        for row in result.result_set
    ]
