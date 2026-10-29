# M3 — Software World

M3 turns the small M1/M2 software graph into a controlled investigation world.

## Objective

Create a software graph where a future investigator must distinguish a
supported multi-hop explanation from distractors and competing hypotheses.

## Investigation question

> Why did `incident-001` happen?

## Ground-truth path

```text
Commit
  ↓ CHANGED
Dependency
  ↓ DEPENDS_ON
Service
  ↓ AFFECTS
Deployment
  ↓ AFFECTS
Metric
  ↓ RESULTED_IN
Incident
```

This is a six-node, five-hop path.

## Adversarial structure

The world also contains:

- a temporally valid infrastructure alternative with missing direct evidence,
- a configuration alternative that occurs after the incident,
- an unrelated software subgraph,
- unrelated infrastructure activity,
- source records for the evidence-backed path.

The dataset therefore supports later milestones for temporal validation,
evidence validation, hypothesis competition, and uncertainty without
hardcoding those reasoning behaviors into M3.

## Gate

Run:

```powershell
uv run python scripts/m3_check.py
```

Expected:

```text
M3 software world check
software_world=PASS
ground_truth_multi_hop_path=PASS hops=5
multiple_hypotheses=PASS
temporal_conflict=PASS
distractors=PASS
missing_evidence=PASS
M3_STATUS=PASS
```

The M3 checker loads the world through the generic `WorldLoader`; it does not
use the M1 hand-written seed graph.

## Boundary

M3 does **not** implement the deterministic investigator. That begins at M6.
M3 provides the controlled world against which that investigator will later be
tested.
