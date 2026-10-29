# Research Question

Status: M0

## Primary Research Question

> Can a reusable graph investigation mechanism reconstruct
> evidence-supported multi-hop explanations across different domains
> without rebuilding the reasoning engine?

## Hypothesis

A domain-independent investigator operating over a typed temporal graph should
be able to recover useful multi-hop explanations across substantially
different worlds, provided that:

1. the world exposes a consistent graph abstraction;
2. relationships carry sufficient provenance;
3. temporal constraints are represented;
4. candidate paths can be compared;
5. explanations are validated before LLM synthesis.

## Independent Variable

The world being investigated.

V1 will use:

- Software
- Supply chain

The investigator should remain unchanged.

## Dependent Measures

The controlled evaluation should measure:

### Path Recovery

Did the investigator recover the intended ground-truth path?

### Evidence Coverage

Are meaningful claims backed by source evidence?

### Unsupported Claim Rate

How often does the system assert relationships that its graph/evidence state
does not support?

### Temporal Consistency

Does the recovered explanation respect event ordering?

### Investigation Efficiency

How many graph operations are required to reach the result?

### Domain Transfer

Does the same investigator operate successfully across both worlds?

## Baseline

The comparison baseline is:

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

Continuum is:

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

Both should use the same underlying information for controlled cases.

## Evaluation Dataset

The V1 plan targets:

- 20 software cases
- 20 supply-chain cases

Each case should contain:

- ground-truth path
- distractor paths
- source evidence
- temporal constraints
- expected answer

## Failure Cases

The system must explicitly test:

### Missing Evidence

Expected:

> Insufficient evidence.

### Multiple Plausible Paths

Expected:

> Multiple explanations remain plausible.

### Temporal Contradiction

Expected:

> Path rejected.

### Misleading Document

Expected:

> Unsupported relationship rejected by graph/evidence validation.

## Falsification / Go-No-Go

The hypothesis is weakened if:

- the investigator requires domain-specific reasoning branches;
- vector retrieval performs equivalently on multi-hop cases;
- graph traversal does not materially contribute to path recovery;
- evidence validation cannot distinguish supported from unsupported claims;
- temporal constraints do not improve rejection of invalid explanations.

The V1 project should not hide these outcomes.

A negative result is still useful if it identifies where graph investigation
does not outperform simpler retrieval.

## Final Research Claim

We do not claim:

> Graphs prove causality.

We do not claim:

> We invented graph RCA.

We claim:

> Continuum tests whether a reusable graph investigation mechanism can
> reconstruct evidence-supported multi-hop explanations across different
> domains using the same investigation architecture.
