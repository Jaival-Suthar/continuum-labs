from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from continuum.core.ontology import (
    CORE_LABELS,
    CORE_RELATIONSHIPS,
    Ontology,
)


@dataclass(frozen=True)
class GraphSchema:
    """Universal graph schema backed by a world ontology."""

    ontology: Ontology = field(default_factory=lambda: Ontology(name="continuum-core"))

    @property
    def labels(self) -> tuple[str, ...]:
        return self.ontology.all_labels

    @property
    def relationships(self) -> tuple[str, ...]:
        return self.ontology.all_relationships

    def validate_relationship(self, relationship: str) -> None:
        self.ontology.validate_relationship(relationship)

    def validate_label(self, label: str) -> None:
        self.ontology.validate_label(label)

    def initialize(self, graph: Any) -> None:
        """Create id indexes for every label in the ontology when missing."""
        result = graph.query("CALL db.indexes()")
        existing_indexes = {
            (row[0], tuple(row[1]))
            for row in result.result_set
            if len(row) > 6 and row[6] == "NODE"
        }

        for label in self.labels:
            if (label, ("id",)) not in existing_indexes:
                graph.query(f"CREATE INDEX FOR (n:{label}) ON (n.id)")


__all__ = ["CORE_LABELS", "CORE_RELATIONSHIPS", "GraphSchema"]
