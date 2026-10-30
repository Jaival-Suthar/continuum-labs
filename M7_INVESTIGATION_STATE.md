# M7 — Persistent Investigation State

## Objective

Turn the deterministic M6 investigation primitives into an actual cumulative
investigation that can continue across multiple explicit reasoning steps.

## Scope

M7 owns:

- `InvestigationState`
- hypothesis state storage
- explored node tracking
- explored edge tracking
- candidate path accumulation
- evidence accumulation
- contradiction accumulation
- evidence-gap accumulation
- temporal constraint accumulation
- investigation history
- deterministic state merging
- idempotent updates
- multi-step continuation verification

M7 does **not** own:

- LLM tool calling
- autonomous agent loops
- ReAct/planning
- evidence validation beyond existing M6 primitives
- hypothesis competition
- report generation
- UI
- counterfactuals

Those belong to later milestones.

## Architecture

```text
                 Investigator
                      |
                      v
             InvestigationState
                      |
        +-------------+-------------+
        |             |             |
     question      hypotheses      target
        |             |             |
        +-------------+-------------+
                      |
                      v
              explicit M7 step
                      |
          +-----------+-----------+
          |           |           |
       explore       trace      validate
          |           |           |
          +-----------+-----------+
                      |
                      v
              existing M6 result
                      |
                      v
              deterministic merge
                      |
                      v
             updated InvestigationState
```

## State contract

`InvestigationState` contains:

```text
question
 target
 hypotheses
 explored_nodes
 explored_edges
 candidate_paths
 evidence
 contradictions
 gaps
 temporal_constraints
 history
 extensions
```

`extensions` is reserved for future capabilities so V2 can extend the state
without changing the V1 core contract.

## Hypothesis contract

M7 stores hypotheses but does not compete them.

```text
Hypothesis
├── id
├── description
├── candidate_path_ids
├── evidence_ids
├── contradictions
├── gaps
└── temporal_constraints
```

The same hypothesis id is merged rather than duplicated.

## Investigation history

Every explicit operation creates an `InvestigationStep` containing:

```text
operation
input
result
state_version
added_nodes
added_edges
added_path_count
added_evidence_count
added_contradiction_count
added_gap_count
added_temporal_constraint_count
```

This makes the investigation traceable without inventing an LLM narrative.

## State update invariant

A result is merged through one mechanism:

```text
M6 operation result
        |
        v
InvestigationState.apply_result()
        |
        +--> nodes
        +--> edges
        +--> paths
        +--> evidence
        +--> contradictions
        +--> gaps
        +--> temporal constraints
        +--> history
```

The merge is idempotent for cumulative collections. Re-running an operation
may create another history entry, but it cannot duplicate the underlying
investigation facts.

## Multi-step proof

The M7 gate executes this sequence:

```text
STATE 0
question = "Why did incident-001 happen?"
target = None
paths = 0

        |
        | find_outcome
        v

STATE 1
target = incident-001

        |
        | expand_neighborhood(depth=2)
        v

STATE 2
explored_nodes += neighborhood

        |
        | trace_backward(max_hops=5, limit=25)
        v

STATE 3
candidate_paths += discovered paths
explored_nodes += path nodes
explored_edges += path edges
evidence/gaps/temporal constraints += path findings

        |
        | evidence + temporal + conflict + ranking operations
        v

STATE 7
all prior state remains available
history contains every step
```

A repeated `trace_backward` must leave the cumulative node, edge, path, and
evidence collections unchanged while adding a history entry.

## Verification

With FalkorDB running:

```bash
docker compose up -d
uv run python scripts/check_falkordb.py
uv run python scripts/m7_check.py
uv run pytest -m "not integration"
uv run pytest
uv run ruff check .
```

The milestone is complete only when `m7_check.py` ends with:

```text
M7 STATUS: PASS
```

The important proof is not the number of fields. It is that later operations
consume the same `InvestigationState` instead of constructing an independent
M6 investigation from scratch.
