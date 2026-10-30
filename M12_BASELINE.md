# M12 — Retrieval-Only Baseline

## Objective

Establish a real control group for V1: the same software-world information is
answered through vector retrieval and an LLM, without invoking Continuum's
investigation engine.

The authoritative V1 plan defines the baseline as:

```text
Question
 ↓
Semantic / vector retrieval
 ↓
Top-k context
 ↓
LLM
 ↓
Answer
```

and contrasts it with graph investigation:

```text
Question
 ↓
Investigation
 ↓
FalkorDB traversal
 ↓
Evidence validation
 ↓
LLM
 ↓
Answer
```

M12 does not claim that Continuum wins. M13 performs the controlled
measurement.

## Architecture

```text
domains/software/WorldData
        │
        ├── nodes
        └── edges
              │
              ▼
       baseline corpus
              │
              ▼
      TF-IDF vector index
              │
              ▼
          top-k context
              │
              ▼
       optional real Ollama
              │
              ▼
       BaselineResult JSON
```

The baseline has no dependency on `GraphClient`, `Investigator`,
`InvestigationState`, FalkorDB traversal, evidence validation, temporal
reasoning, hypothesis competition, or M11 reporting.

The corpus is built directly from `SOFTWARE_WORLD`'s declared nodes and edges.
That keeps the underlying information constant with the Continuum world while
changing the reasoning mechanism.

## Retrieval

M12 uses deterministic TF-IDF weighted term vectors with cosine similarity.
This is a real vector-space retrieval implementation with no external
embedding service required.

Tie-breaking is deterministic by document id. The retrieved document ids,
source ids, context, and similarity scores are retained in the result.

This is intentionally not described as neural semantic embeddings. If M13
later requires a neural embedding control, it can be introduced as a separate
controlled variable.

## LLM boundary

`OllamaBaselineLLM` calls Ollama's `/api/chat` endpoint with:

- the question,
- only retrieved documents,
- no tools,
- no graph access,
- an explicit instruction to avoid unsupported claims.

A missing Ollama server or model is a real failure in `--mode ollama`; no fake
answer is substituted.

## Machine-readable result

Each run captures:

- `question`
- `world`
- `top_k`
- `retrieved_ids`
- `retrieved_source_ids`
- `retrieved_context`
- `retrieval_scores`
- `answer`
- `model`
- `created_at`

The JSON artifact is suitable for M13 without requiring a new output format.

## Verification

### 1. Static/unit baseline verification

```powershell
uv run pytest tests/test_m12_baseline_unit.py -q
```

Expected:

```text
6 passed
```

### 2. Full non-integration suite

```powershell
uv run pytest -m "not integration" -q
```

Expected:

```text
92 passed, 18 deselected
```

The exact total can increase if additional tests are added after M12; the
important requirement is zero failures.

### 3. Lint

```powershell
uv run ruff check .
```

Expected:

```text
All checks passed!
```

### 4. Retrieval-only gate

This mode does not require FalkorDB or Ollama and therefore validates the
control-group construction independently:

```powershell
uv run python scripts/m12_check.py --mode retrieval
```

Expected shape:

```text
CONTINUUM · M12
World                  software
Corpus documents       38
Question               Why did incident-001 happen?
Top-k                  8
Retrieved              8
LLM                    not requested
...
Same software world data       PASS
Vector retrieval               PASS · deterministic TF-IDF cosine retrieval
Top-k context                  PASS · 8 documents
Graph investigation            PASS · no GraphClient, FalkorDB, or Investigator used
Structured result              PASS · question/context/source ids/scores captured
LLM answer                     NOT RUN · use --mode ollama for the real LLM step

M12 STATUS: PASS
```

The exact retrieved document ids and floating-point scores are implementation
output and should be inspected from the JSON artifact rather than treated as
hard-coded evaluation results.

### 5. Real LLM gate

Install/start Ollama and ensure the requested model is actually present.
Then run:

```powershell
$env:CONTINUUM_LLM_MODEL="qwen3:8b"
uv run python scripts/m12_check.py --mode ollama --model $env:CONTINUUM_LLM_MODEL
```

Expected shape when Ollama and the model are genuinely available:

```text
CONTINUUM · M12
World                  software
Corpus documents       38
Question               Why did incident-001 happen?
Top-k                  8
Retrieved              8
LLM                    qwen3:8b
...
LLM answer                     PASS · real Ollama response captured

BASELINE ANSWER

<real Ollama answer>

M12 STATUS: PASS
```

If Ollama is unavailable or the model is missing, this command must fail. That
is intentional: M12 never fabricates a model response.

## Scope boundary

M12 does not add:

- evaluation metrics,
- 20-case software benchmark,
- 20-case supply-chain benchmark,
- failure suite,
- UI,
- graph traversal to the baseline,
- hypothesis competition,
- evidence validation inside the baseline,
- autonomous investigation.

Those belong to later milestones or the existing Continuum engine.
