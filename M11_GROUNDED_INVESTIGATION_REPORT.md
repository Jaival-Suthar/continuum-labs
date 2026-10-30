# M11 — Grounded Investigation Report

M11 is Continuum's deterministic presentation boundary.

It consumes an already-grounded M6-M10 `InvestigationResult` or M7
`InvestigationState` and turns that state into a user-facing report.

## Architecture

```text
M8 Agent
   ↓
Investigation
   ↓
M9 Evidence Validation
   ↓
M10 Hypothesis Competition
   ↓
validated Investigation State
   ↓
M11 Report Builder
   ↓
Grounded Investigation Report
```

M11 does not investigate.

It performs no:

- graph queries
- evidence validation
- temporal reasoning
- hypothesis scoring
- path discovery
- LLM synthesis
- investigation planning

## Report contract

`InvestigationReport` contains:

- Question
- Most Supported Explanation
- Evidence Path
- Observed Facts
- Derived Relationships
- Supported Inferences
- Contradictions
- Unknowns / Evidence Gaps
- Sources
- Investigation Trace

Each report statement carries references to the structured evidence, path,
or hypothesis data from which it was produced.

## Uncertainty preservation

M10 has three valid outcomes.

### Winner

```text
H1 best supported
```

M11 renders the winning hypothesis as the most supported explanation.

### Ambiguous

```text
H1, H2 remain plausible
```

M11 renders:

```text
Multiple explanations remain plausible.

H1 — Dependency change
H2 — Configuration change

The available evidence does not justify selecting one over the other.
```

M11 never collapses this into a single winner.

### Insufficient

```text
Insufficient evidence
```

M11 renders:

```text
Insufficient evidence.
```

M11 never manufactures a confidence percentage.

## Public API

```python
from continuum.report import GroundedReportBuilder, format_report

report = GroundedReportBuilder().from_state(investigation_state)

print(format_report(report))
```

For an already-produced deterministic result:

```python
report = GroundedReportBuilder().from_result(investigation_result)
```

The state boundary requires the M10
`hypothesis_competition` extension.

This prevents M11 from silently inventing a verdict.

## Verification

### M11 unit tests

```bash
uv run pytest tests/test_m11_grounded_report_unit.py -q
```

Expected:

```text
6 passed
```

### Real FalkorDB M11 gate

```bash
uv run python scripts/m11_check.py
```

Expected final status:

```text
M11 STATUS: PASS
```

The gate verifies:

- real FalkorDB connectivity
- real seeded software graph
- real M10 candidate paths
- real deterministic M10 competition
- report generation from state
- evidence preservation
- path preservation
- contradiction preservation
- evidence-gap preservation
- source preservation
- investigation trace preservation
- no confidence synthesis

### Full non-integration suite

```bash
uv run pytest -m "not integration" -q
```

Expected:

```text
<all non-integration tests passed>
```

### Full suite

Requires FalkorDB:

```bash
uv run pytest -q
```

Expected:

```text
<all tests passed>
```

### Lint

```bash
uv run ruff check .
```

Expected:

```text
All checks passed!
```

## Completion criterion

M11 is complete when the same grounded investigation state answers both:

> What does Continuum think happened?

and:

> Why does Continuum think that?

without performing any new investigation or introducing unsupported claims.