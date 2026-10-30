# M10 — Hypothesis Competition

M10 prevents premature commitment to the first plausible explanation.

It adds a deterministic competition layer above the existing M6 investigator,
M7 investigation state, M8 control loop, and M9 evidence validator.

## Boundary

```text
M8 LLM controller
      |
      | proposes/investigates; does not score or choose
      v
M7 InvestigationState
      |
      v
M6 candidate paths
      |
      v
M9 relationship validation
      |
      +--> support
      +--> contradiction
      +--> missing evidence
      +--> temporal validity
      +--> path quality
      |
      v
M10 deterministic ranking
      |
      +--> H1 best supported
      +--> H1 and H2 remain plausible
      +--> Insufficient evidence
```

## Deterministic hypothesis model

`continuum.hypothesis.Hypothesis` is an evaluated hypothesis. It contains:

- `id`
- `claim`
- `supporting_evidence`
- `contradictions`
- `missing_evidence`
- `temporal_validity`
- `candidate_paths`
- `path_quality`
- deterministic `score`
- the individual M9 `claim_validations`

The M7 `continuum.core.Hypothesis` remains the persistent proposal/state
object. M10 converts that state object into the evaluated hypothesis above.
Candidate paths are identified by a stable hash of their actual graph node IDs,
relationship types, and edge IDs.

## Evaluation

For every candidate path attached to a hypothesis, M10 derives one M9 `Claim`
per graph hop and calls the existing `Investigator.validate_claim()` boundary.
No LLM value is accepted for support, contradiction, evidence status, or
temporal validity.

### Path quality

Path quality is ordinal, not probabilistic:

- **STRONG** — temporally valid, every hop has provenance evidence, and every
  hop is evidence-backed by M6 provenance.
- **MODERATE** — temporally valid with some evidence-backed support, but not a
  complete strong path.
- **WEAK** — temporal conflict, missing evidence, conflicting evidence, or no
  evidence-backed hop.

### Score

M10 uses one transparent integer score:

```text
score = support + temporal + path_quality - contradiction - missing_evidence
```

Where:

- `support` = number of unique M9-validated claims classified as supported.
- `temporal` = valid candidate paths minus invalid candidate paths.
- `path_quality` = STRONG 2, MODERATE 1, WEAK 0.
- `contradiction` = number of unique contradiction records.
- `missing_evidence` = number of unique missing-evidence records.

This is an ordinal ranking signal. It is **not a confidence percentage** and is
never presented as probability.

## Competition outcomes

The ranker has exactly three outcomes:

### Winner

A single plausible hypothesis has the highest score:

```text
H1 best supported
```

### Ambiguous

Two or more plausible hypotheses share the highest score:

```text
H1, H2 remain plausible
```

### Insufficient

No hypothesis has positive M9 support together with a valid candidate path and
no contradiction:

```text
Insufficient evidence
```

M10 never forces a winner in the latter two cases.

## M8 integration

The existing `compare_hypotheses` M8 tool is now the deterministic M10
boundary. The LLM can request the operation, but the operation itself calls
`Investigator.compete_hypotheses()` and stores the resulting structured
competition in `InvestigationState.extensions["hypothesis_competition"]`.

The LLM receives the computed result as state/tool context and remains an
interpreter/controller. It does not calculate the score or select the winner.

M8's other tools and control loop are unchanged.

## Verification

Unit tests:

```bash
uv run pytest tests/test_m10_hypothesis_competition_unit.py
```

M10 real FalkorDB gate:

```bash
uv run python scripts/m10_check.py
```

Full non-integration suite:

```bash
uv run pytest -m "not integration"
```

Full suite with FalkorDB running:

```bash
uv run pytest
```

Lint:

```bash
uv run ruff check .
```

## Real software-world proof

The M10 gate loads the existing M3 software world and discovers three actual
FalkorDB paths:

```text
H1 Dependency change
commit-001
  -> dependency-gateway-sdk
  -> service-payments
  -> deployment-001
  -> metric-001
  -> incident-001

H2 Infrastructure event
infra-event-001
  -> metric-001
  -> incident-001

H3 Configuration change
config-001
  -> metric-001
  -> incident-001
```

The existing dataset makes H1 evidence-backed, H2 missing provenance, and H3
temporally invalid. M10 therefore must return:

```text
H1 best supported
```

The unit suite independently proves the two other competition outcomes:

```text
H1, H2 remain plausible
```

and:

```text
Insufficient evidence
```

No synthetic confidence percentages are used.
