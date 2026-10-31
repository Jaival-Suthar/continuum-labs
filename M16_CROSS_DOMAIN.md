# M16 — Cross-Domain Gate

M16 is the defining V1 architecture gate. It proves that the same investigation machinery can investigate the Software and Supply-Chain worlds without domain-specific Investigator logic.

## Gate

```text
                 SAME INVESTIGATOR
                    /         \
                   /           \
                  ↓             ↓
          SOFTWARE WORLD   SUPPLY-CHAIN WORLD
                  \             /
                   \           /
                    ↓         ↓
              SHARED INVESTIGATION
```

The gate runs both worlds against FalkorDB, then verifies the same implementation is responsible for:

- graph search/traversal and temporal operations,
- `InvestigationState` / `InvestigationResult`,
- hypothesis evaluation,
- evidence validation,
- grounded reporting.

It also statically rejects known domain-specific Investigator branches.

## Real execution

`scripts/m16_check.py` uses one `Investigator` instance. It loads the Software world, investigates the incident, validates the primary and competing paths, then resets the same FalkorDB graph, loads Supply Chain, and repeats the investigation with the same Investigator implementation.

The M16 artifact contains:

```text
artifacts/m16/
    software_run.json
    supply_chain_run.json
    cross_domain_summary.json
```

All values in those files are derived from the actual FalkorDB investigation and deterministic validation pipeline. No confidence values or fabricated metrics are introduced.

## Acceptance criteria

M16 passes only when:

1. Software investigation succeeds.
2. Supply-Chain investigation succeeds.
3. Both use the same `Investigator` implementation.
4. Both use the same graph-operation layer.
5. Both use the same investigation-state/result models.
6. Both use the same hypothesis evaluator.
7. Both use the same evidence validator.
8. Both use the same report builder.
9. Evidence is present on the expected primary paths.
10. Temporal validation accepts the primary paths and rejects the fixture conflict paths.
11. Competing hypotheses remain represented by the shared hypothesis machinery.
12. FalkorDB performs the actual graph investigation.
13. M14 and M15 remain regression gates.

M16 does not add another domain, a new causal algorithm, counterfactual reasoning, monitoring, memory, policy learning, or UI work.
