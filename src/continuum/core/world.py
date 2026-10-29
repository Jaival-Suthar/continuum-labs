from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from continuum.core.models import GraphEdge, GraphNode
from continuum.core.ontology import Ontology, TemporalModel


class WorldData(Protocol):
    """Minimal data adapter contract understood by the universal graph loader."""

    def nodes(self) -> tuple[GraphNode, ...]: ...
    def edges(self) -> tuple[GraphEdge, ...]: ...


@dataclass(frozen=True)
class World:
    """Domain package consumed by the investigator without domain-specific branches."""

    name: str
    ontology: Ontology
    data: WorldData
    temporal_model: TemporalModel = field(default_factory=TemporalModel)

    def validate(self) -> None:
        if not self.name:
            raise ValueError("World.name must not be empty")

        valid_temporal_fields = {
            "timestamp",
            "valid_from",
            "valid_until",
            "observed_at",
        }
        valid_temporal_operations = {
            "before",
            "after",
            "between",
            "preceded_by",
            "valid_at",
        }
        if not set(self.temporal_model.fields) <= valid_temporal_fields:
            raise ValueError("World temporal model contains unsupported fields")
        if not set(self.temporal_model.operations) <= valid_temporal_operations:
            raise ValueError("World temporal model contains unsupported operations")

        node_ids: set[str] = set()
        for node in self.data.nodes():
            self.ontology.validate_label(node.label)
            if node.id in node_ids:
                raise ValueError(f"Duplicate node id in world '{self.name}': {node.id}")
            node_ids.add(node.id)

        for edge in self.data.edges():
            self.ontology.validate_relationship(edge.relationship)
            if edge.source_id not in node_ids:
                raise ValueError(f"Unknown edge source: {edge.source_id}")
            if edge.target_id not in node_ids:
                raise ValueError(f"Unknown edge target: {edge.target_id}")
