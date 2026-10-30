# M13 — Controlled Evaluation

M13 measures Continuum against the **M12 retrieval-only control** on the same controlled evaluation cases.

## Scope

* 20 software cases.
* 20 supply-chain cases.
* Every case declares ground truth independently of any Continuum execution.
* Both systems receive the same case `World` data and question.
* The baseline uses **M12 TF-IDF retrieval only**. It does not invoke the Continuum investigator or perform FalkorDB graph investigation.
* Continuum uses the existing deterministic investigator over FalkorDB.
* M13 evaluates **structured investigation outcomes**, not subjective natural-language answer quality.

The controlled cases are benchmark fixtures created specifically for evaluation. They are not presented as production-world observations. Their ground truth is explicit benchmark data, so the evaluation remains reproducible and non-circular.

**M13 is therefore a controlled structural evaluation of retrieval-only versus graph investigation. It is not yet the final LLM-powered RAG-versus-Continuum experiment.**

## Case contract

Each case persists:

* `case_id`
* `domain`
* `question`
* `ground_truth_path`
* `ground_truth_edge_ids`
* `distractor_paths`
* `source_evidence`
* `temporal_constraints`
* `expected_answer`
* `expected_edge_evidence`

Ground truth and expected answers are declared as benchmark data before execution and are never generated from Continuum results.

## Metrics

### Path recovery

Exact path recovery is the headline metric. Node and edge precision/recall are also persisted to expose partial recovery.

### Evidence coverage

For explicitly reconstructed relationship claims, the evaluator checks whether the declared supporting source evidence is present.

No LLM judges evidence support.

### Unsupported claim rate

`unsupported_claims / claims_evaluated` for the structured relationships reconstructed by each system.

This is deliberately narrower than a subjective natural-language hallucination rate. It measures unsupported structured relationships, not whether an entire generated answer "sounds correct."

### Temporal consistency

Every declared temporal constraint is evaluated directly from the case timestamps.

No LLM makes temporal decisions.

### Investigation efficiency

Continuum records actual graph operations performed during investigation, including the graph calls and available investigation-state measurements such as explored nodes, explored edges, investigation trace steps, and elapsed time.

No synthetic complexity score is introduced.

### Domain transfer interface

The runner accepts either domain through the same `EvaluationCase` and `ControlledEvaluationRunner` contract.

M13 establishes the domain-independent evaluation interface. The definitive cross-domain investigator proof remains M16.

## Artifacts

```text
artifacts/m13/
├── cases/
│   ├── software/
│   └── supply_chain/
├── runs/
│   ├── software/
│   └── supply_chain/
└── summary.json
```

Each executed case produces a persisted result containing the inputs, system outputs, and metric inputs required to reproduce the aggregate calculations.

All numbers in `summary.json` are calculated from executed case results. No benchmark metric is hard-coded.

## Explicit M13 boundary

M13 does **not** claim that Continuum outperforms a full LLM-powered RAG system.

The later evaluation will use the same controlled questions and information to compare:

```text
LLM + retrieval-only RAG
            vs
LLM + Continuum investigation
```

That experiment will be performed separately after the V1 investigation/failure and cross-domain capabilities are complete.

M13's purpose is to establish a reproducible, non-circular measurement layer for Continuum's graph investigation capabilities.
