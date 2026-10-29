from __future__ import annotations

from dataclasses import dataclass

CORE_LABELS = (
    "Entity",
    "Event",
    "Change",
    "Observation",
    "Outcome",
    "Source",
)

CORE_RELATIONSHIPS = (
    "AFFECTS",
    "DEPENDS_ON",
    "CHANGED",
    "PRECEDED",
    "RESULTED_IN",
    "OBSERVED_AS",
    "SUPPORTED_BY",
    "MENTIONED_IN",
    "OWNED_BY",
)


@dataclass(frozen=True)
class GraphSchema:
    labels: tuple[str, ...] = CORE_LABELS
    relationships: tuple[str, ...] = CORE_RELATIONSHIPS

    def validate_relationship(self, relationship: str) -> None:
        if relationship not in self.relationships:
            raise ValueError(f"Unsupported core relationship: {relationship}")

    def validate_label(self, label: str) -> None:
        if label not in self.labels:
            raise ValueError(f"Unsupported core label: {label}")

    def initialize(self, graph) -> None:
        existing_indexes = {
            (row[0], tuple(row[1]))
            for row in graph.query("CALL db.indexes()").result_set
            if row[6] == "NODE"
        }

        for label in self.labels:
            if (label, ("id",)) not in existing_indexes:
                graph.query(f"CREATE INDEX FOR (n:{label}) ON (n.id)")
