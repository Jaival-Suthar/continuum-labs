# Software investigation world

M3 is the primary Continuum demo world.

The dataset intentionally models an investigation rather than a single happy
path. It contains:

- a six-node ground-truth path from commit to incident,
- an infrastructure alternative with missing direct evidence,
- a configuration alternative that occurs after the incident,
- an unrelated software subgraph as a distractor,
- source records for the evidence-backed path,
- temporal metadata on relevant events and relationships.

The intended investigation question is:

> Why did `incident-001` happen?

Ground-truth path:

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

M3 does not implement the investigator's reasoning logic. It creates the
controlled world required to test that logic in later milestones.
