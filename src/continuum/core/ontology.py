from __future__ import annotations

import re
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

_CYPHER_TOKEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Ontology:
    """A world ontology: universal core semantics plus optional domain extensions."""

    name: str
    labels: tuple[str, ...] = CORE_LABELS
    relationships: tuple[str, ...] = CORE_RELATIONSHIPS
    label_extensions: tuple[str, ...] = ()
    relationship_extensions: tuple[str, ...] = ()

    @property
    def all_labels(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.labels, *self.label_extensions)))

    @property
    def all_relationships(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys((*self.relationships, *self.relationship_extensions))
        )

    def validate_label(self, label: str) -> None:
        if label not in self.all_labels:
            raise ValueError(f"Unsupported label for ontology '{self.name}': {label}")
        if not _CYPHER_TOKEN.fullmatch(label):
            raise ValueError(f"Invalid graph label: {label}")

    def validate_relationship(self, relationship: str) -> None:
        if relationship not in self.all_relationships:
            raise ValueError(
                f"Unsupported relationship for ontology '{self.name}': {relationship}"
            )
        if not _CYPHER_TOKEN.fullmatch(relationship):
            raise ValueError(f"Invalid graph relationship: {relationship}")


@dataclass(frozen=True)
class TemporalModel:
    """Common temporal vocabulary shared by every world."""

    fields: tuple[str, ...] = (
        "timestamp",
        "valid_from",
        "valid_until",
        "observed_at",
    )
    operations: tuple[str, ...] = (
        "before",
        "after",
        "between",
        "preceded_by",
        "valid_at",
    )
