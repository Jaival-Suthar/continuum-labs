# M6 — Deterministic Investigation Engine

M6 turns the M1–M5 graph foundation into a reusable deterministic investigation layer.

## Scope

The engine exposes:

- `find_outcome()`
- `find_related_entities()`
- `expand_neighborhood()`
- `find_paths()`
- `trace_backward()`
- `trace_forward()`
- `find_preceding_changes()`
- `find_downstream_impact()`
- `find_supporting_evidence()`
- `find_conflicting_evidence()`
- `check_temporal_consistency()`
- `rank_paths()`

The complete `investigate()` pipeline performs graph lookup, FalkorDB traversal, M5 temporal classification, M4 provenance resolution, contradiction/gap collection, and transparent deterministic ranking before any LLM synthesis.

## Important guarantees

1. FalkorDB performs the graph lookup and traversal.
2. Paths are returned from actual graph traversal; they are not manually assembled in Python.
3. M5 event-time validation classifies every discovered candidate as `VALID`, `INVALID`, or `UNKNOWN`.
4. M4 provenance is resolved from the relationship's `evidence_source_ids`.
5. Temporal conflicts and evidence contradictions are surfaced instead of silently discarded.
6. Missing evidence is represented explicitly as a gap.
7. Ranking uses observable deterministic signals only; no invented confidence percentage is emitted.
8. The investigator contains no software/supply-chain reasoning branch.
9. `InvestigationResult` is structured for later M7/M8/M9 milestones.

## Verification

Run the M6 verification script after starting FalkorDB:

```powershell
uv run python scripts/m6_check.py
```

Run the full suite:

```powershell
uv run pytest -q
```

Run lint:

```powershell
uv run ruff check .
```
> M6 is considered verified only when the M6 verification script, full test suite, and lint checks pass.