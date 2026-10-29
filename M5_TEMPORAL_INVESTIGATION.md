# M5 — Temporal Investigation

M5 makes time a deterministic graph constraint. It does not implement causal
inference, hypothesis scoring, LLM reasoning, or a general temporal database.

## Contract

Supported temporal metadata:

- `timestamp`: when an event/change/relationship occurred.
- `valid_from`: when a state/relationship became valid.
- `valid_until`: when a state/relationship stopped being valid.
- `observed_at`: when a source observed/reported a fact.

`timestamp` and `observed_at` are distinct. Investigation ordering uses event
time (`timestamp`); source observation time is provenance metadata.

## Deterministic operations

`continuum.temporal` provides:

- `before(a, b)`
- `after(a, b)`
- `between(value, start, end)`
- `preceded_by(event, reference)`
- `valid_at(entity, timestamp)`

Missing temporal information returns `None`, represented by the temporal
status `UNKNOWN`. It is never silently treated as valid.

## FalkorDB operations

`TemporalQueries` performs graph-backed:

- event ordering queries,
- state-at-time queries,
- candidate path discovery,
- temporal path classification.

Evidence-only `SUPPORTED_BY` relationships are excluded from temporal candidate
path discovery so provenance edges do not create false investigation paths.

## Path semantics

For a discovered path, known node `timestamp` values must be non-decreasing.

Example:

```text
09:00 commit
09:20 deployment
09:45 metric
10:00 incident
```

is `VALID`.

This is rejected:

```text
10:30 configuration
09:45 metric
10:00 incident
```

with:

```text
INVALID
reason = event occurs after a later event in path
```

A path with no usable event timestamps is:

```text
UNKNOWN
```

This is a temporal admissibility decision, not a causal proof.

## State-at-time

Configuration state is represented with validity intervals:

```text
config-A
08:00 <= valid < 09:10

config-B
09:10 <= valid <= 10:00
```

Therefore:

```text
valid_at(config-B, 09:20) -> True
```

and the FalkorDB state query at `09:20` returns `config-B`.

## Verification

Start FalkorDB:

```bash
docker compose up -d
```

Run the M5 gate:

```bash
uv run python scripts/m5_check.py
```

Run unit tests:

```bash
uv run pytest -m "not integration"
```

Run integration tests:

```bash
uv run pytest -m integration
```

Run the complete suite:

```bash
uv run pytest
```

Run lint:

```bash
uv run ruff check .
```

M5 is complete only when all commands pass. The central gate is the
deterministic rejection of a cause that occurs after its effect.
