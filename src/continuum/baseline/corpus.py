from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from continuum.core.models import GraphEdge, GraphNode
from continuum.core.world import World


@dataclass(frozen=True)
class CorpusDocument:
    """One retrieval unit derived directly from the world's source data."""

    id: str
    text: str
    source_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("CorpusDocument.id must not be empty")
        if not self.text.strip():
            raise ValueError("CorpusDocument.text must not be empty")
        object.__setattr__(self, "source_ids", tuple(dict.fromkeys(self.source_ids)))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True)
class BaselineCorpus:
    """Immutable retrieval corpus for one world snapshot."""

    world_name: str
    documents: tuple[CorpusDocument, ...]

    def __post_init__(self) -> None:
        ids = [doc.id for doc in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("BaselineCorpus document ids must be unique")
        if not self.documents:
            raise ValueError("BaselineCorpus must contain at least one document")


def _timestamp_fields(item: GraphNode | GraphEdge) -> list[str]:
    fields: list[str] = []
    for name in ("timestamp", "valid_from", "valid_until", "observed_at"):
        value = getattr(item, name, None)
        if isinstance(value, datetime):
            fields.append(f"{name}={value.isoformat()}")
    return fields


def _node_document(node: GraphNode, edges: tuple[GraphEdge, ...]) -> CorpusDocument:
    related = [
        edge for edge in edges if edge.source_id == node.id or edge.target_id == node.id
    ]
    lines = [
        f"node_id: {node.id}",
        f"label: {node.label}",
        f"name: {node.name}",
        *_timestamp_fields(node),
    ]
    for key in sorted(node.properties):
        lines.append(f"property {key}: {node.properties[key]}")
    for edge in related:
        direction = "outgoing" if edge.source_id == node.id else "incoming"
        lines.append(
            f"{direction} relationship: {edge.source_id} -[{edge.relationship}]-> "
            f"{edge.target_id}"
        )
        if edge.timestamp:
            lines.append(f"relationship_timestamp: {edge.timestamp.isoformat()}")
        if edge.evidence_source_ids:
            lines.append(
                "relationship_evidence_sources: " + ", ".join(edge.evidence_source_ids)
            )
    source_ids = tuple(
        source_id for edge in related for source_id in edge.evidence_source_ids
    )
    return CorpusDocument(
        id=f"node:{node.id}",
        text="\n".join(lines),
        source_ids=source_ids,
        metadata={"kind": "node", "node_id": node.id, "label": node.label},
    )


def _edge_document(
    edge: GraphEdge, nodes_by_id: dict[str, GraphNode]
) -> CorpusDocument:
    source = nodes_by_id[edge.source_id]
    target = nodes_by_id[edge.target_id]
    lines = [
        f"edge_id: {edge.stable_id}",
        f"source: {source.id} ({source.label}) {source.name}",
        f"relationship: {edge.relationship}",
        f"target: {target.id} ({target.label}) {target.name}",
        *_timestamp_fields(edge),
        f"evidence_status: {edge.evidence_status}",
    ]
    if edge.evidence_source_ids:
        lines.append("evidence_sources: " + ", ".join(edge.evidence_source_ids))
    for key in sorted(edge.properties):
        lines.append(f"property {key}: {edge.properties[key]}")
    return CorpusDocument(
        id=f"edge:{edge.stable_id}",
        text="\n".join(lines),
        source_ids=edge.evidence_source_ids,
        metadata={
            "kind": "edge",
            "edge_id": edge.stable_id,
            "source_id": edge.source_id,
            "relationship": edge.relationship,
            "target_id": edge.target_id,
        },
    )


def build_corpus(world: World) -> BaselineCorpus:
    """Materialize the same world data into retrieval documents.

    No graph client, traversal, investigator, validation, or hypothesis
    machinery is involved. The corpus is derived from the world's declared
    nodes and edges, so the baseline sees the same underlying information.
    """
    world.validate()
    nodes = world.data.nodes()
    edges = world.data.edges()
    nodes_by_id = {node.id: node for node in nodes}
    documents = [
        *(_node_document(node, edges) for node in nodes),
        *(_edge_document(edge, nodes_by_id) for edge in edges),
    ]
    return BaselineCorpus(world_name=world.name, documents=tuple(documents))
