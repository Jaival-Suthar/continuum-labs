# M9 — Evidence Validator

M9 adds the deterministic boundary that decides what a proposed relationship
is actually supported by the graph and its evidence.

## Invariant

> **The LLM may propose a claim, but only Continuum's deterministic validation
> layer may classify its evidentiary status.**

The LLM remains an interpreter. FalkorDB remains the source of graph facts.

## Pipeline

```text
Claim
  ↓
graph validation
  ↓
evidence lookup (M4 provenance)
  ↓
temporal check (M5 temporal machinery)
  ↓
contradiction check (M6 conflict primitive semantics)
  ↓
evidence classification
```

## Claim

```python
Claim(
    subject="commit-001",
    relationship="CHANGED",
    object="dependency-gateway-sdk",
)
```

The validator only accepts a relationship that exists as the exact directed
edge `(subject)-[:REL]->(object)` in FalkorDB.

## Classification

M9 uses the V1 evidence model:

- `OBSERVED` — direct graph relationship with observed source evidence and a
  temporally admissible claim.
- `DERIVED` — relationship/evidence explicitly marked derived.
- `SUPPORTED_INFERENCE` — relationship/evidence explicitly marked as a
  supported inference.
- `CONTRADICTED` — temporal impossibility or explicit contradictory evidence.
- `UNKNOWN` — the relationship is absent, evidence is missing, or temporal
  validity cannot be established.

`UNKNOWN` is not converted to false or true. The user-facing message is:

`Insufficient evidence.`

## M4–M6 Composition

M9 does not replace the deterministic investigation primitives built earlier.

It composes:

- M4 provenance resolution for evidence lookup.
- M5 temporal machinery for temporal consistency.
- M6 `find_conflicting_evidence()` semantics for contradiction detection.

The final evidentiary classification is owned by M9.

## Real LLM Integration

M9 was verified with a real Ollama model against a real FalkorDB instance.

The integration flow is:

```text
Ollama model
    ↓
M8 AgenticInvestigator
    ↓
propose_claim(subject, relationship, object)
    ↓
Claim
    ↓
M9 EvidenceValidator
    ↓
graph → evidence → temporal → contradiction → classification
```

The model is only permitted to propose:

- `subject`
- `relationship`
- `object`

The model does not provide:

- evidence classification
- confidence
- verdict
- supporting evidence
- evidentiary status

For the real integration test, the model proposed:

```text
commit-001 -[CHANGED]-> dependency-gateway-sdk
```

M9 independently classified the claim as:

```text
OBSERVED
```

A controlled unsupported relationship was also submitted directly to M9 and
classified as:

```text
UNKNOWN
```

with the user-facing result:

```text
Insufficient evidence.
```

This demonstrates the M9 authority boundary:

> The LLM proposes a claim. Continuum determines whether the claim is supported.

## What M9 does not do

- no final report generation (M11)
- no hypothesis competition (M10)
- no confidence percentage
- no second LLM
- no UI
- no domain-specific investigator branch

## Verification

### Offline deterministic gate

```powershell
uv run python scripts/m9_check.py --mode deterministic
```

### Real FalkorDB gate

```powershell
uv run python scripts/m9_check.py --mode falkordb
```

### Real Ollama + FalkorDB integration gate

```powershell
uv run python scripts/m9_check.py --mode ollama --model qwen3:8b
```

The Ollama gate verifies:

- real Ollama connectivity
- real FalkorDB graph loading
- real M8 investigation execution
- real LLM claim proposal
- deterministic M9 validation
- unsupported-claim rejection
- LLM authority boundary

### M9 unit tests

```powershell
uv run pytest tests/test_m9_evidence_validator_unit.py -q
```

### Full test suite

```powershell
uv run pytest
```

### Lint

```powershell
uv run ruff check .
```