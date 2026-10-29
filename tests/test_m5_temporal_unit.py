from datetime import UTC, datetime

from continuum.temporal import (
    TEMPORAL_UNKNOWN,
    after,
    before,
    between,
    check_cause_before_effect,
    check_temporal_sequence,
    preceded_by,
    valid_at,
)


def dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 8, 1, hour, minute, tzinfo=UTC)


def test_before_after_and_between_are_deterministic():
    assert before(dt(9), dt(10)) is True
    assert after(dt(10), dt(9)) is True
    assert between(dt(9, 30), dt(9), dt(10)) is True
    assert between(dt(10), dt(9), dt(10)) is True


def test_missing_time_is_unknown_for_ordering():
    assert before(None, dt(10)) is None
    assert after(dt(10), None) is None
    assert between(None, dt(9), dt(10)) is None
    assert preceded_by(None, dt(10)) is None


def test_valid_at_uses_validity_interval():
    state = {"valid_from": dt(9), "valid_until": dt(10)}
    assert valid_at(state, dt(9, 30)) is True
    assert valid_at(state, dt(10, 1)) is False


def test_valid_at_returns_unknown_without_temporal_metadata():
    assert valid_at({}, dt(9, 30)) is None


def test_valid_at_uses_occurrence_timestamp_when_no_interval_exists():
    event = {"timestamp": dt(9)}
    assert valid_at(event, dt(9)) is True
    assert valid_at(event, dt(9, 1)) is False


def test_temporal_sequence_accepts_ordered_path():
    result = check_temporal_sequence(
        ["commit", "deployment", "metric", "incident"],
        [
            {"timestamp": dt(9)},
            {"timestamp": dt(9, 20)},
            {"timestamp": dt(9, 45)},
            {"timestamp": dt(10)},
        ],
    )
    assert result.valid is True
    assert result.status == "VALID"


def test_temporal_sequence_rejects_reversed_event_time():
    result = check_temporal_sequence(
        ["cause", "effect"],
        [{"timestamp": dt(11)}, {"timestamp": dt(10)}],
    )
    assert result.valid is False
    assert result.reason == "event occurs after a later event in path"
    assert result.violating_events == ("cause", "effect")


def test_temporal_sequence_returns_unknown_when_all_times_are_missing():
    result = check_temporal_sequence(
        ["a", "b"],
        [{"name": "A"}, {"name": "B"}],
    )
    assert result.valid is None
    assert result.status == TEMPORAL_UNKNOWN


def test_cause_after_effect_is_rejected():
    result = check_cause_before_effect(
        "config-001",
        {"timestamp": dt(10, 30)},
        "incident-001",
        {"timestamp": dt(10)},
    )
    assert result.valid is False
    assert result.reason == "cause occurs after effect"


def test_observed_at_does_not_replace_event_timestamp():
    result = check_cause_before_effect(
        "event",
        {"timestamp": dt(9), "observed_at": dt(9, 10)},
        "incident",
        {"timestamp": dt(9, 5)},
    )
    assert result.valid is True


def test_temporal_sequence_uses_relationship_event_time():
    result = check_temporal_sequence(
        ["a", "b"],
        [{"name": "A"}, {"name": "B"}],
        [{"edge_id": "edge-1", "timestamp": dt(11)}],
    )
    # There is only one known anchor, so there is no ordering contradiction.
    assert result.valid is True


def test_temporal_sequence_rejects_edge_after_target_event():
    result = check_temporal_sequence(
        ["a", "b"],
        [{"timestamp": dt(9)}, {"timestamp": dt(10)}],
        [{"edge_id": "edge-1", "timestamp": dt(11)}],
    )
    assert result.valid is False
    assert result.violating_events == ("edge:edge-1", "b")
