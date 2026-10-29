from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from continuum.graph.client import GraphClient
from continuum.temporal.model import (
    TemporalCheck,
    check_temporal_sequence,
    format_timestamp,
    parse_timestamp,
)


@dataclass(frozen=True)
class TemporalPath:
    """A FalkorDB path plus the node/edge temporal metadata returned with it."""

    node_ids: tuple[str, ...]
    relationships: tuple[str, ...]
    node_timestamps: tuple[str | None, ...]
    edge_timestamps: tuple[str | None, ...]
    node_records: tuple[dict[str, Any], ...]
    edge_records: tuple[dict[str, Any], ...]

    @property
    def temporal_check(self) -> TemporalCheck:
        return check_temporal_sequence(
            self.node_ids, self.node_records, self.edge_records
        )


@dataclass(frozen=True)
class TemporalPathResult:
    path: TemporalPath
    check: TemporalCheck


class TemporalQueries:
    """FalkorDB-backed temporal query boundary.

    The graph performs path discovery and temporal state lookup. Deterministic
    Python validation then evaluates the returned event-time sequence. This
    keeps temporal admissibility independent of any LLM.
    """

    def __init__(self, client: GraphClient):
        self.client = client

    def ordering(
        self,
        node_id: str,
        *,
        before_timestamp: str,
        limit: int = 50,
    ) -> list[list[Any]]:
        """Return all graph events before an anchor's event time, ordered."""
        if limit < 1:
            raise ValueError("limit must be >= 1")
        anchor = self.client.read(
            "MATCH (n {id:$node_id}) RETURN n.timestamp",
            {"node_id": node_id},
        )
        if not anchor.result_set or anchor.result_set[0][0] is None:
            raise ValueError(f"node {node_id} has no timestamp")
        requested = parse_timestamp(before_timestamp)
        anchor_time = parse_timestamp(anchor.result_set[0][0])
        if requested is None or anchor_time is None:
            raise ValueError("ordering requires valid timestamps")
        if requested != anchor_time:
            raise ValueError(
                f"before_timestamp {format_timestamp(requested)} does not match "
                f"{node_id} timestamp {format_timestamp(anchor_time)}"
            )

        result = self.client.read(
            f"""
            MATCH (candidate)
            WHERE candidate.timestamp IS NOT NULL
              AND candidate.timestamp < $before_timestamp
            RETURN
                candidate.id,
                labels(candidate),
                candidate.name,
                candidate.timestamp
            ORDER BY candidate.timestamp ASC, candidate.id ASC
            LIMIT {int(limit)}
            """,
            {
                "before_timestamp": format_timestamp(anchor_time),
            },
        )
        return result.result_set

    def state_at(self, timestamp: str, *, label: str | None = None) -> list[list[Any]]:
        """Return graph states active at an instant using valid_from/valid_until."""
        point = parse_timestamp(timestamp)
        if point is None:
            raise ValueError("timestamp is required")

        if label is not None and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", label):
            raise ValueError(f"invalid graph label: {label}")
        label_clause = f":{label}" if label else ""
        result = self.client.read(
            f"""
            MATCH (n{label_clause})
            WHERE n.valid_from IS NOT NULL
              AND n.valid_from <= $timestamp
              AND (n.valid_until IS NULL OR n.valid_until >= $timestamp)
            RETURN
                n.id,
                labels(n),
                n.name,
                n.valid_from,
                n.valid_until,
                n.timestamp,
                n.observed_at
            ORDER BY n.valid_from ASC, n.id ASC
            """,
            {"timestamp": format_timestamp(point)},
        )
        return result.result_set

    def paths_between(
        self,
        start_id: str,
        end_id: str,
        *,
        max_hops: int = 6,
        limit: int = 25,
    ) -> list[TemporalPath]:
        """Discover candidate paths in FalkorDB with evidence edges excluded."""
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")
        if limit < 1:
            raise ValueError("limit must be >= 1")

        result = self.client.read(
            f"""
            MATCH p=(start {{id:$start_id}})-[*1..{int(max_hops)}]-(end {{id:$end_id}})
            WHERE ALL(r IN relationships(p) WHERE type(r) <> 'SUPPORTED_BY')
            RETURN nodes(p), relationships(p)
            LIMIT {int(limit)}
            """,
            {"start_id": start_id, "end_id": end_id},
        )

        paths: list[TemporalPath] = []
        for row in result.result_set:
            nodes, edges = row
            node_records = tuple(dict(node.properties) for node in nodes)
            edge_records = tuple(dict(edge.properties) for edge in edges)
            node_ids = tuple(record.get("id") for record in node_records)
            relationships = tuple(edge.relation for edge in edges)
            node_timestamps = tuple(record.get("timestamp") for record in node_records)
            edge_timestamps = tuple(record.get("timestamp") for record in edge_records)

            if any(node_id is None for node_id in node_ids):
                raise ValueError("temporal path contains a node without stable id")

            paths.append(
                TemporalPath(
                    tuple(str(node_id) for node_id in node_ids),
                    relationships,
                    node_timestamps,
                    edge_timestamps,
                    node_records,
                    edge_records,
                )
            )
        return paths

    def filter_temporal_paths(
        self,
        paths: Sequence[TemporalPath],
    ) -> list[TemporalPathResult]:
        """Classify candidates without silently treating unknown time as valid."""
        return [TemporalPathResult(path, path.temporal_check) for path in paths]

    def temporally_valid_paths(
        self,
        start_id: str,
        end_id: str,
        *,
        max_hops: int = 6,
        limit: int = 25,
    ) -> list[TemporalPathResult]:
        """Discover and retain only VALID temporal paths."""
        return [
            result
            for result in self.filter_temporal_paths(
                self.paths_between(
                    start_id,
                    end_id,
                    max_hops=max_hops,
                    limit=limit,
                )
            )
            if result.check.valid is True
        ]
