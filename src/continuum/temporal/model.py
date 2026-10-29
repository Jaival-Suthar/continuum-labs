from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any

TEMPORAL_UNKNOWN = "UNKNOWN"
TEMPORAL_VALID = "VALID"
TEMPORAL_INVALID = "INVALID"


def parse_timestamp(value: Any) -> datetime | None:
    """Normalize FalkorDB/string/Python datetime values to timezone-aware UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        dt = datetime.fromisoformat(text)
    else:
        raise TypeError(f"Unsupported temporal value: {type(value).__name__}")

    if dt.tzinfo is None:
        raise ValueError("Temporal values must be timezone-aware")
    return dt.astimezone(UTC)


def format_timestamp(value: datetime) -> str:
    """Return the canonical UTC representation persisted by the graph loader."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class TemporalMetadata:
    """Temporal fields supported by the V1 temporal contract."""

    timestamp: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("timestamp", "valid_from", "valid_until", "observed_at"):
            value = getattr(self, name)
            if value is not None:
                parse_timestamp(value)
        if (
            self.valid_from
            and self.valid_until
            and parse_timestamp(self.valid_from) > parse_timestamp(self.valid_until)
        ):
            raise ValueError("valid_from must be <= valid_until")


@dataclass(frozen=True)
class TemporalCheck:
    """Deterministic result of a temporal admissibility check.

    ``valid`` is True for VALID, False for INVALID and None for UNKNOWN.
    UNKNOWN is intentionally distinct from both valid and invalid.
    """

    valid: bool | None
    reason: str
    violating_events: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        if self.valid is True:
            return TEMPORAL_VALID
        if self.valid is False:
            return TEMPORAL_INVALID
        return TEMPORAL_UNKNOWN


def _time(value: Any) -> datetime | None:
    return parse_timestamp(value)


def before(a: Any, b: Any) -> bool | None:
    """Return whether temporal point ``a`` occurs strictly before ``b``."""
    left, right = _time(a), _time(b)
    if left is None or right is None:
        return None
    return left < right


def after(a: Any, b: Any) -> bool | None:
    """Return whether temporal point ``a`` occurs strictly after ``b``."""
    left, right = _time(a), _time(b)
    if left is None or right is None:
        return None
    return left > right


def between(value: Any, start: Any, end: Any) -> bool | None:
    """Return whether ``value`` lies in the inclusive [start, end] interval."""
    point, lower, upper = _time(value), _time(start), _time(end)
    if point is None or lower is None or upper is None:
        return None
    if lower > upper:
        raise ValueError("between() requires start <= end")
    return lower <= point <= upper


def preceded_by(event: Any, reference: Any) -> bool | None:
    """Alias with investigation-oriented wording: event precedes reference."""
    return before(event, reference)


def valid_at(entity: Any, timestamp: Any) -> bool | None:
    """Evaluate whether a state/relationship is valid at ``timestamp``.

    ``entity`` may be a mapping/object exposing ``valid_from`` and
    ``valid_until``. If neither validity bound exists, a ``timestamp`` field
    is treated as an occurrence time and is valid only at that exact instant.
    Missing temporal information returns None (UNKNOWN).
    """
    point = _time(timestamp)
    if point is None:
        return None

    if isinstance(entity, dict):
        get = entity.get
    else:
        get = lambda key, default=None: getattr(entity, key, default)

    start = _time(get("valid_from"))
    end = _time(get("valid_until"))

    if start is None and end is None:
        occurrence = _time(get("timestamp"))
        return None if occurrence is None else occurrence == point

    if start is not None and point < start:
        return False
    return not (end is not None and point > end)


def effective_time(item: Any) -> datetime | None:
    """Get the event/state time used for ordering, never observed_at by default.

    Investigation ordering is based on event/state time. ``observed_at`` is
    source observation time and is deliberately only a fallback when no event
    time exists; callers that require strict event-time semantics should treat
    a missing event time as UNKNOWN.
    """
    if isinstance(item, dict):
        get = item.get
    else:
        get = lambda key, default=None: getattr(item, key, default)
    return _time(get("timestamp"))


def _iter_ordered_times(
    node_ids: Iterable[str],
    node_records: Iterable[dict[str, Any]],
) -> tuple[list[tuple[str, datetime]], list[str]]:
    records = list(node_records)
    times: list[tuple[str, datetime]] = []
    missing: list[str] = []
    for node_id, record in zip(node_ids, records):
        timestamp = effective_time(record)
        if timestamp is None:
            missing.append(node_id)
        else:
            times.append((node_id, timestamp))
    return times, missing


def check_temporal_sequence(
    node_ids: Iterable[str],
    node_records: Iterable[dict[str, Any]],
    edge_records: Iterable[dict[str, Any]] | None = None,
) -> TemporalCheck:
    """Check known event timestamps in path order.

    Node and relationship occurrence times are treated as temporal anchors.
    Missing intermediate timestamps do not invalidate a path, but if no
    timestamp exists anywhere the result is UNKNOWN. Known anchors must be
    non-decreasing along the path.
    """
    ids = list(node_ids)
    records = list(node_records)
    if len(ids) != len(records):
        raise ValueError("node_ids and node_records must have the same length")

    edges = list(edge_records or [])
    if edges and len(edges) != max(0, len(ids) - 1):
        raise ValueError("edge_records must contain one record per path hop")

    anchors: list[tuple[str, datetime]] = []
    for index, node_id in enumerate(ids):
        node_time = effective_time(records[index])
        if node_time is not None:
            anchors.append((node_id, node_time))

        if index < len(edges):
            edge_time = effective_time(edges[index])
            if edge_time is not None:
                anchors.append(
                    (f"edge:{edges[index].get('edge_id', index)}", edge_time)
                )

    if not anchors:
        return TemporalCheck(None, "missing temporal metadata", tuple(ids))

    for (left_id, left_time), (right_id, right_time) in pairwise(anchors):
        if right_time < left_time:
            return TemporalCheck(
                False,
                "event occurs after a later event in path",
                (left_id, right_id),
            )

    return TemporalCheck(True, "path temporally consistent")


def check_cause_before_effect(
    cause_id: str,
    cause_record: dict[str, Any],
    effect_id: str,
    effect_record: dict[str, Any],
) -> TemporalCheck:
    """Check the central M5 invariant: cause/event time must not follow effect."""
    cause_time = effective_time(cause_record)
    effect_time = effective_time(effect_record)

    if cause_time is None or effect_time is None:
        missing = tuple(
            node_id
            for node_id, record in (
                (cause_id, cause_record),
                (effect_id, effect_record),
            )
            if effective_time(record) is None
        )
        return TemporalCheck(None, "missing temporal metadata", missing)

    if cause_time > effect_time:
        return TemporalCheck(
            False,
            "cause occurs after effect",
            (cause_id, effect_id),
        )

    return TemporalCheck(True, "cause occurs before or at effect")
