# M8 — Agentic Investigator

M8 adds the LLM control loop on top of the deterministic M6 investigator and
persistent M7 state.

## Boundary

```text
M7 InvestigationState
        ↓
LLMProvider
        ↓
choose one investigation tool
        ↓
M8 schema + allowlist validation
        ↓
M6 Investigator operation
        ↓
FalkorDB facts
        ↓
M7 InvestigationState.apply_result()
        ↓
tool result + current state
        ↓
LLMProvider
        ↓
...
```

The LLM chooses an operation. Continuum executes it. FalkorDB remains the
source of graph facts. M7 retains the cumulative investigation state.

## M8 tools

- `search_entities` → M6 `find_outcome`
- `query_graph` → M6 `find_paths` using structured IDs; no arbitrary Cypher
- `expand_node` → M6 `expand_neighborhood`
- `trace_backward` → M6 `trace_backward`
- `trace_forward` → M6 `trace_forward`
- `find_paths` → M6 `find_paths`
- `find_changes` → M6 `find_preceding_changes`
- `find_evidence` → M6 `find_supporting_evidence`
- `check_temporal_consistency` → M6 `check_temporal_consistency`
- `compare_hypotheses` → read-only M7 hypothesis inspection; it does not score,
  rank, validate, or select a winning hypothesis. Hypothesis competition remains
  M10.

Every executable graph operation crosses the existing M6/M7 boundary.

## LLM providers

`LLMProvider` is provider-neutral. `OllamaProvider` uses Ollama's local HTTP
API and is not a hard dependency of M1–M7.

Environment variables:

```powershell
$env:CONTINUUM_LLM_PROVIDER="ollama"
$env:CONTINUUM_OLLAMA_MODEL="qwen3:30b-a3b-instruct-2507-q4_K_M"
```

## Verification

Offline deterministic gate:

```powershell
uv run python scripts/m8_check.py --mode deterministic
```

Real Ollama + FalkorDB gate:

```powershell
uv run python scripts/m8_check.py --mode ollama --model qwen3:30b-a3b-instruct-2507-q4_K_M
```

The real gate fails if Ollama, the requested model, or FalkorDB is unavailable.
It never substitutes a fake response for a missing service.

Tests:

```powershell
uv run pytest -q
uv run pytest -m "not integration" -q
uv run pytest -m integration -q
uv run ruff check .
```

The Ollama integration test is opt-in because it requires the user's local
Ollama service:

```powershell
$env:CONTINUUM_RUN_OLLAMA_TEST="1"
uv run pytest -m integration -q
```

## Current model experimentation

M8 was exercised against the same investigation environment using multiple
local Ollama models. The graph, M6 investigator, M7 state model, tool registry,
and configured step budget were kept unchanged between model runs.

Three runs were collected for each model.

| Model | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| `qwen3:8b` | 3 steps · `DONE` | 9 steps · `MAX_STEPS` | 4 steps · `DONE` |
| `gpt-oss:20b` | 6 steps · `MAX_STEPS` | 5 steps · `MAX_STEPS` | 4 steps · `MAX_STEPS` |
| `deepseek-r1:8b` | tool-selection failure | Ollama timeout | tool-selection failure |
| `llama3.1:8b` | 7 steps · `MAX_STEPS` | 10 steps · `MAX_STEPS` | 10 steps · `MAX_STEPS` |
| `qwen3:30b-a3b-instruct-2507-q4_K_M` | 10 steps · `MAX_STEPS` | 10 steps · `MAX_STEPS` | 10 steps · `MAX_STEPS` |

These runs demonstrate that different LLMs can produce materially different
investigation trajectories while operating against the same Continuum
interface.

Observed behavior included:

- `qwen3:8b` produced variable trajectories and explicitly terminated in two
  of three runs.
- `gpt-oss:20b` repeatedly used backward tracing and supporting-evidence
  operations, with all three runs reaching the configured step limit.
- `llama3.1:8b` repeatedly selected `find_outcome`, reaching the step limit in
  all three runs.
- `qwen3:30b-a3b-instruct-2507-q4_K_M` explored a broader combination of
  backward tracing, paths, preceding changes, neighborhood expansion,
  supporting evidence, and temporal consistency, but reached the step limit
  in all three runs.
- `deepseek-r1:8b` did not reliably produce an executable investigation tool
  call in two available model runs. One additional run was an Ollama
  connectivity timeout and is treated as an infrastructure failure rather
  than a model-behavior observation.

These observations are exploratory rather than a statistical benchmark.
`DONE` and `MAX_STEPS` are recorded separately; `M8 STATUS: PASS` is the
engineering verification result and is not a model-quality score.

The experiment does not change the M8 architecture or introduce
model-specific behavior into Continuum.


## Scope exclusions

M8 does not add claim validation, evidence classification beyond existing M6
results, hypothesis competition, reporting, UI, or autonomous remediation.
