# M17 — Investigation UI

M17 is the human-facing projection of the existing deterministic investigation engine.

## Architecture

```text
Browser
   ↓ JSON/HTTP
M17 API
   ↓
Investigator
   ↓
Graph traversal + temporal validation + provenance + hypothesis competition
   ↓
FalkorDB
```

The browser does not issue Cypher, calculate hypothesis scores, validate timestamps, or decide whether relationships are supported.

## API

- `GET /api/health`
- `GET /api/worlds`
- `POST /api/investigations`
- `GET /api/investigations/{id}`
- `GET /api/investigations/{id}/graph`
- `GET /api/investigations/{id}/evidence?id={evidence_id}`

## UI contract

The investigation page exposes:

- question and domain context
- investigation status
- verdict / ambiguity / insufficient-evidence state
- graph nodes and relationships from actual investigation paths
- path alternatives and temporal status
- actual investigation trace
- provenance evidence
- deterministic hypothesis competition
- node/relationship/evidence inspection
- reloadable persisted investigation state

No fabricated confidence or fake trace events are generated.

## Run

```powershell
uv run python scripts/m17_server.py
```

Then open `http://127.0.0.1:8000`.

## Verification

```powershell
uv run python scripts/m17_check.py
uv run pytest tests/test_m17_api.py -q
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

The complete M17 gate requires a reachable FalkorDB instance.
