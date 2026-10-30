# M14 — Failure Suite

M14 extends the controlled evaluation infrastructure with four adversarial failure families. It verifies that the existing investigation stack exposes uncertainty or rejects unsupported paths when evidence is insufficient, competing explanations remain viable, temporal ordering is impossible, or a misleading source proposes a relationship that the graph does not support.

## Failure families

| Case | Fixture condition | Expected behavior |
|---|---|---|
| `m14-missing-evidence` | A graph path exists but one required relationship has no provenance evidence | `Insufficient evidence.` |
| `m14-multiple-plausible-paths` | Two independent paths have complete evidence and valid temporal order | `Multiple explanations remain plausible.` |
| `m14-temporal-contradiction` | A candidate cause occurs after the outcome | `Path rejected.` |
| `m14-misleading-document` | Retrieval can surface a document asserting an unsupported relationship | `Unsupported relationship rejected.` |

The expected behavior is authored in each fixture. It is never generated from the investigator result.

## Architecture

M14 does not add failure-specific investigator branches.

```text
Failure fixture
    ↓
WorldLoader
    ↓
FalkorDB
    ↓
Existing Investigator
    ↓
Path discovery
    ↓
Existing provenance/evidence validation
    ↓
Existing temporal validation
    ↓
Existing M10 hypothesis competition
    ↓
M14 assertions + persisted result
```

The misleading-document case additionally runs the existing M12 TF-IDF retrieval boundary to demonstrate that a misleading source can be retrieved while the M9 graph/evidence boundary still rejects its unsupported relationship.

## Code

```text
src/continuum/failure/
├── __init__.py
├── model.py
├── cases.py
└── runner.py

scripts/
└── m14_check.py

tests/
└── test_m14_failure_suite_unit.py
```

## Artifacts

A successful run creates:

```text
artifacts/m14/
├── cases/
│   ├── missing_evidence/
│   ├── multiple_plausible_paths/
│   ├── temporal_contradiction/
│   └── misleading_document/
├── runs/
│   ├── missing_evidence/
│   ├── multiple_plausible_paths/
│   ├── temporal_contradiction/
│   └── misleading_document/
└── summary.json
```

The case artifacts contain the authored expected state and serialized world fixture. The run artifacts contain the actual graph-derived paths, evidence, contradictions, temporal checks, hypothesis evaluations, retrieval observations where applicable, and validation result.

The aggregate `pass_rate` is calculated from the executed case result records. It is never hard-coded.

## Verification

Start FalkorDB:

```powershell
docker compose up -d
```

Run the complete suite:

```powershell
uv run python scripts/m14_check.py
```

Run one failure family:

```powershell
uv run python scripts/m14_check.py --failure-type missing-evidence
uv run python scripts/m14_check.py --failure-type multiple-plausible-paths
uv run python scripts/m14_check.py --failure-type temporal-contradiction
uv run python scripts/m14_check.py --failure-type misleading-document
```

Run one exact case:

```powershell
uv run python scripts/m14_check.py --case m14-missing-evidence
```

Run deterministic tests:

```powershell
uv run pytest -q
```

Check formatting/lint:

```powershell
uv run ruff format --check .
uv run ruff check .
```

The M14 CLI intentionally fails when FalkorDB cannot be reached. There is no in-memory fallback for the integration gate.

## Definition of done

M14 is complete when:

- all four failure families are independently declared;
- the investigator is not given the expected answer;
- actual FalkorDB operations occur;
- missing evidence produces an insufficient result;
- competing valid paths remain ambiguous;
- temporal contradictions are rejected;
- misleading retrieved relationships are rejected by graph/evidence validation;
- M10 hypothesis competition is exercised;
- results are persisted per case;
- the aggregate is calculated from executed results;
- deterministic tests pass;
- Ruff passes; and
- the real FalkorDB integration gate passes.

M14 is therefore a failure-behavior gate over the existing V1 investigation architecture, not a second investigator.
