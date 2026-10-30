# Continuum

General-purpose graph investigation engine.

## V1 foundation

- FalkorDB-backed graph investigation
- Domain-independent investigation core
- Evidence and provenance
- Temporal validation
- Software and supply-chain worlds

## M1 — FalkorDB foundation

Start FalkorDB:

```bash
docker compose up -d
```

Check connectivity:

```bash
python scripts/check_falkordb.py
```

Run unit tests:

```bash
pytest -m "not integration"
```

Run the FalkorDB integration check:

```bash
pytest -m integration
```

M1 deliberately establishes the graph infrastructure before introducing an
LLM or agent. The graph must be able to perform investigation work directly.


## M2 — Universal core model

M2 defines the domain-independent semantic contract used by Continuum.

Core objects:

- `Entity`
- `Event`
- `Change`
- `Observation`
- `Outcome`
- `Source`

Core relationships:

- `AFFECTS`
- `DEPENDS_ON`
- `CHANGED`
- `PRECEDED`
- `RESULTED_IN`
- `OBSERVED_AS`
- `SUPPORTED_BY`
- `MENTIONED_IN`
- `OWNED_BY`

A `World` supplies an ontology, data adapter, and temporal model. The
investigator and graph loader consume that contract without branching on the
domain. Software and supply-chain packages demonstrate two different worlds
using the same universal core.

Validate the M2 contract without FalkorDB:

```bash
uv run pytest -m "not integration"
```

Validate both domain packages against FalkorDB:

```bash
uv run python scripts/m2_check.py
uv run pytest -m integration
```


## M3 — Software investigation world

M3 replaces the minimal software example with a controlled investigation
scenario designed to make graph reasoning non-trivial.

The software world contains:

- a six-node ground-truth path from commit to incident,
- a temporally valid infrastructure alternative with missing evidence,
- a configuration alternative that occurs after the incident,
- unrelated graph distractors,
- source records for the evidence-backed path,
- temporal metadata on relevant events and relationships.

The intended question is:

> Why did `incident-001` happen?

Run the M3 gate against FalkorDB:

```bash
uv run python scripts/m3_check.py
```

M3 deliberately does not implement investigator reasoning. It creates the
controlled world required for M6-M11, where traversal, temporal validation,
evidence validation, and hypothesis competition are implemented.


## M4 — Provenance

M4 makes graph relationships auditable before the investigation engine is
built.

Relationships now have stable identity and explicit provenance fields:

- `edge_id`
- `evidence_status`
- `evidence_source_ids`
- temporal metadata
- `provenance_version`

Source records expose:

- `record`
- `span`
- `observed_at`
- `status`

The provenance resolver returns the relationship together with its resolved
source evidence. Missing evidence is represented explicitly as
`evidence_status=UNKNOWN`; the system does not manufacture support.

Run the M4 gate against FalkorDB:

```bash
uv run python scripts/m4_check.py
```

Expected:

```text
M4 provenance check
relationship_identity=PASS edges=17
source_records=PASS sources=5
primary_path_provenance=PASS
missing_evidence_explicit=PASS
M4_STATUS=PASS
```

Run the full non-integration suite:

```bash
uv run pytest -m "not integration"
```

M4 still does not implement temporal path filtering, hypothesis competition,
agentic investigation, or LLM synthesis. Those remain later milestones.


## M5 — Temporal investigation

M5 makes time a real graph constraint.

Temporal metadata has explicit semantics:

- `timestamp` — event/change/relationship occurrence time
- `valid_from` / `valid_until` — state validity interval
- `observed_at` — source observation/reporting time

The temporal layer provides deterministic `before`, `after`, `between`,
`preceded_by`, and `valid_at` operations plus FalkorDB-backed ordering,
state-at-time queries, and temporal path filtering.

A path whose known event timestamps reverse order is rejected. A path with no
usable temporal metadata is `UNKNOWN`, not silently valid. Event time is never
replaced by source observation time.

Run the M5 gate:

```bash
uv run python scripts/m5_check.py
```

Run the complete verification suite:

```bash
uv run pytest
uv run ruff check .
```

The M5 scenario proves:

```text
09:30 incident
   ↑
10:00 supposed cause

=> REJECTED
```

M5 does not implement causal inference or LLM reasoning. It establishes
temporal admissibility for M6's deterministic investigation engine.
## M6 — Deterministic investigation engine

M6 turns the M1–M5 graph foundation into a reusable deterministic investigation
layer.

The investigator now combines FalkorDB graph traversal, M5 temporal validation,
and M4 relationship provenance to produce structured, auditable investigation
results without LLM-generated reasoning.

### What was implemented

- Added deterministic outcome discovery.
- Added related-entity lookup and neighborhood expansion.
- Added multi-hop path discovery using FalkorDB.
- Added backward and forward graph tracing.
- Added preceding-change discovery using temporal ordering.
- Added downstream impact analysis.
- Added relationship-level supporting evidence resolution.
- Added explicit conflicting-evidence detection.
- Added explicit missing-evidence gap tracking.
- Added temporal consistency checks using M5.
- Added deterministic path ranking using observable graph/evidence signals.
- Extended `InvestigationResult` for structured investigation output.
- Preserved the M2 universal `Investigator.investigate()` contract.
- Kept the investigator domain-independent with no software-specific or
  supply-chain-specific reasoning branches.

### Verification

M1 verification: PASS

M2 verification: PASS

M3 verification: PASS

M4 verification: PASS

M5 verification: PASS

M6 verification: PASS

M6 verifies:

- Real FalkorDB multi-hop traversal
- Temporal `VALID` / `INVALID` / `UNKNOWN` classification
- M4 provenance consumption
- Supporting evidence resolution
- Evidence gaps
- Temporal/evidence conflicts
- Deterministic path ranking
- No invented confidence scores
- No LLM synthesis

Commands:

```bash
uv run python scripts/m6_check.py
uv run pytest -q
uv run ruff check .

## M7 — Persistent investigation state

M7 turns the deterministic M6 primitives into a cumulative investigation. The
state is separate from `InvestigationResult`: an M6 result describes one
operation, while `InvestigationState` retains the discoveries needed by the
next operation.

The state contains:

- `question`
- `target`
- `hypotheses`
- `explored_nodes`
- `explored_edges`
- `candidate_paths`
- `evidence`
- `contradictions`
- `gaps`
- `temporal_constraints`
- `history`
- `extensions`

M7 adds explicit deterministic continuation through:

```python
state = investigator.start_investigation(
    "Why did incident-001 happen?",
    hypotheses=(
        Hypothesis("H1", "Dependency change"),
        Hypothesis("H2", "Configuration change"),
        Hypothesis("H3", "Infrastructure event"),
    ),
)

investigator.continue_investigation(state, "find_outcome")
investigator.continue_investigation(state, "expand_neighborhood", depth=2)
investigator.continue_investigation(
    state,
    "trace_backward",
    max_hops=5,
    limit=25,
)
```

Each operation delegates to an existing M6 primitive, then passes its
`InvestigationResult` through one deterministic state-update mechanism.
Collections are idempotently merged, while `history` records every operation
and the state version at which it completed. No LLM, autonomous planning,
hypothesis competition, reporting, or UI is introduced by M7.

Run the M7 gate against FalkorDB:

```bash
uv run python scripts/m7_check.py
```

Run the M7 unit tests:

```bash
uv run pytest tests/test_m7_investigation_state_unit.py
```

Run all non-integration tests:

```bash
uv run pytest -m "not integration"
```

Run the complete verification suite with FalkorDB running:

```bash
uv run pytest
uv run ruff check .
```

The M7 gate proves that step 2 consumes state produced by step 1, step 3
consumes the same continuing investigation, and repeating an operation does not
duplicate explored nodes, explored edges, candidate paths, or evidence.

M8 remains responsible for allowing an LLM to choose which investigation
operation should run next.

## M8 — Agentic investigator

M8 adds the LLM control loop on top of the deterministic M6 investigator and
persistent M7 investigation state.

The LLM is a controller, not the source of graph truth. It chooses the next
allowlisted investigation operation; Continuum validates and executes that
operation through the existing investigator; FalkorDB supplies graph facts; M7
retains the cumulative investigation state; and the resulting tool result and
current state are returned to the LLM for the next decision.

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

### M8 investigation tools

The LLM can select only the following investigation operations:

- `search_entities` → M6 `find_outcome`
- `query_graph` → M6 `find_paths` using structured IDs; no arbitrary Cypher
- `expand_node` → M6 `expand_neighborhood`
- `trace_backward` → M6 `trace_backward`
- `trace_forward` → M6 `trace_forward`
- `find_paths` → M6 `find_paths`
- `find_changes` → M6 `find_preceding_changes`
- `find_evidence` → M6 `find_supporting_evidence`
- `check_temporal_consistency` → M6 `check_temporal_consistency`
- `compare_hypotheses` → read-only M7 hypothesis inspection

Every executable graph operation crosses the existing M6/M7 boundary.

`compare_hypotheses` only inspects hypotheses already stored in M7. It does
not score, rank, validate, or select a winning hypothesis. Hypothesis
competition remains a later milestone.

### LLM providers

`LLMProvider` is provider-neutral.

M8 currently provides `OllamaProvider`, which communicates with a local
Ollama HTTP API. Ollama is optional and is not a dependency of M1–M7.

Example configuration:

```powershell
$env:CONTINUUM_LLM_PROVIDER="ollama"
$env:CONTINUUM_OLLAMA_MODEL="qwen3:30b-a3b-instruct-2507-q4_K_M"
```

The provider boundary allows different local models to operate against the
same Continuum investigation interface without changing M6, M7, or the graph
execution layer.

### Verification

Run the deterministic M8 gate without Ollama:

```powershell
uv run python scripts/m8_check.py --mode deterministic
```

Run the real Ollama + FalkorDB gate:

```powershell
$env:CONTINUUM_LLM_PROVIDER="ollama"
$env:CONTINUUM_OLLAMA_MODEL="qwen3:30b-a3b-instruct-2507-q4_K_M"

uv run python scripts/m8_check.py --mode ollama --model $env:CONTINUUM_OLLAMA_MODEL
```

The real gate deliberately fails when Ollama, the selected model, or FalkorDB
is unavailable. It never substitutes a fake model response for a missing
service.

Run the complete test suite:

```powershell
uv run pytest -q
```

Run only non-integration tests:

```powershell
uv run pytest -m "not integration" -q
```

Run integration tests:

```powershell
uv run pytest -m integration -q
```

The real Ollama integration test is opt-in:

```powershell
$env:CONTINUUM_RUN_OLLAMA_TEST="1"
uv run pytest -m integration -q
```

Run linting:

```powershell
uv run ruff check .
```

### Model experimentation

M8 was exercised against multiple local Ollama models while keeping the
Continuum investigation environment unchanged. The graph, M6 investigator,
M7 state model, tool registry, and configured step budget were kept constant
between runs.

Three cluster runs were collected for each model.

| Model | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| `qwen3:8b` | 3 steps · `DONE` | 9 steps · `MAX_STEPS` | 4 steps · `DONE` |
| `gpt-oss:20b` | 6 steps · `MAX_STEPS` | 5 steps · `MAX_STEPS` | 4 steps · `MAX_STEPS` |
| `deepseek-r1:8b` | tool-selection failure | Ollama timeout | tool-selection failure |
| `llama3.1:8b` | 7 steps · `MAX_STEPS` | 10 steps · `MAX_STEPS` | 10 steps · `MAX_STEPS` |
| `qwen3:30b-a3b-instruct-2507-q4_K_M` | 10 steps · `MAX_STEPS` | 10 steps · `MAX_STEPS` | 10 steps · `MAX_STEPS` |

Observed trajectories included:

- `qwen3:8b` produced variable investigation paths and explicitly
  terminated in two of three runs.
- `gpt-oss:20b` repeatedly used backward tracing and supporting-evidence
  operations and reached the configured step limit in all three runs.
- `llama3.1:8b` repeatedly selected `find_outcome` and reached the step limit
  in all three runs.
- `qwen3:30b-a3b-instruct-2507-q4_K_M` explored a broader combination of
  backward tracing, paths, preceding changes, neighborhood expansion,
  supporting evidence, and temporal consistency, while reaching the step
  limit in all three runs.
- `deepseek-r1:8b` did not reliably produce an executable investigation tool
  call in two available model runs. One additional run was an Ollama
  connectivity timeout and is treated as an infrastructure failure rather
  than a model-behavior observation.

These results are exploratory observations, not a statistical model benchmark.
`DONE` and `MAX_STEPS` are intentionally treated as different outcomes when
analyzing model behavior.

The experimentation does not introduce model-specific behavior into
Continuum. The same deterministic investigation interface remains in place
for each provider.

### Scope exclusions

M8 does not add:

- claim validation,
- new evidence classification beyond existing M6 results,
- hypothesis competition,
- reporting,
- UI,
- autonomous remediation.

Those remain outside the M8 boundary.

## M9 — Evidence validator

M9 adds the deterministic boundary that prevents an LLM-proposed relationship
from being presented as an established fact without graph and evidence support.

The LLM may propose a `Claim`; only `EvidenceValidator` assigns its evidentiary
classification.

The validation pipeline is fixed:

```text
Claim
  ↓
graph validation
  ↓
evidence lookup
  ↓
temporal check
  ↓
contradiction check
  ↓
evidence classification
```

The validator returns one of the V1 evidence states:

- `OBSERVED`
- `DERIVED`
- `SUPPORTED_INFERENCE`
- `CONTRADICTED`
- `UNKNOWN`

`UNKNOWN` is explicit and is rendered as `Insufficient evidence.` rather than
being converted to a boolean truth value or an invented confidence score.

M9 composes the existing M4 provenance resolver, M5 temporal machinery, and
M6 `find_conflicting_evidence()` primitive. It does not add reporting,
hypothesis competition, UI, or another LLM.

### Real LLM integration

M9 has been verified with a real Ollama model against a real FalkorDB instance.

The model proposes only the claim:

```text
subject
relationship
object
```

The deterministic M9 validator independently determines the evidentiary status.

For the real integration test, the model proposed:

```text
commit-001 -[CHANGED]-> dependency-gateway-sdk
```

M9 independently classified the claim as:

```text
OBSERVED
```

A controlled unsupported relationship was classified as:

```text
UNKNOWN
```

and surfaced as:

```text
Insufficient evidence.
```

This verifies the M9 authority boundary:

> The LLM proposes a claim. Continuum determines whether the claim is supported.

### Run the deterministic M9 gate

```powershell
uv run python scripts/m9_check.py --mode deterministic
```

### Run the real FalkorDB M9 gate

```powershell
uv run python scripts/m9_check.py --mode falkordb
```

### Run the real Ollama + FalkorDB M9 gate

```powershell
uv run python scripts/m9_check.py --mode ollama --model qwen3:8b
```

### Run the M9 unit tests

```powershell
uv run pytest tests/test_m9_evidence_validator_unit.py -q
```

### Run the full test suite

```powershell
uv run pytest
```

### Run lint

```powershell
uv run ruff check .
```
