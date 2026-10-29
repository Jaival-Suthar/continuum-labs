# M2 — Universal Core Model

## Objective

Create the domain-independent graph model so different worlds can be represented
without changing the investigator.

## Universal objects

- `Entity`
- `Event`
- `Change`
- `Observation`
- `Outcome`
- `Source`

## Core relationships

- `AFFECTS`
- `DEPENDS_ON`
- `CHANGED`
- `PRECEDED`
- `RESULTED_IN`
- `OBSERVED_AS`
- `SUPPORTED_BY`
- `MENTIONED_IN`
- `OWNED_BY`

## World contract

A `World` contains:

```text
World
├── name
├── ontology
├── data
└── temporal_model
```

The data adapter exposes only:

```text
nodes()
edges()
```

The ontology combines the universal core with domain extensions.

The graph loader consumes this contract generically. It does not contain
software-specific or supply-chain-specific branches.

## Domain proof

Two worlds are included:

```text
domains/
├── software/
│   ├── ontology.py
│   ├── schema.py
│   ├── data.py
│   └── world.py
└── supply_chain/
    ├── ontology.py
    ├── schema.py
    ├── data.py
    └── world.py
```

Software uses extensions such as `Commit`, `Dependency`, `Service`, and
`Deployment`. Supply chain uses `Supplier`, `Component`, `Factory`, and
`Shipment`.

Both are represented through the same `GraphNode`, `GraphEdge`, `World`,
`GraphSchema`, and `WorldLoader` contracts.

## Boundary

M2 does **not** implement deterministic investigation primitives, temporal
path filtering, hypothesis competition, agentic investigation, or reporting.
Those are later milestones.

The investigator remains a domain-independent boundary and accepts a `World`
contract rather than a domain selector.

## Gate

M2 passes when:

1. The universal objects and relationships have stable programmatic models.
2. A world validates its nodes, edges, ontology, and endpoints.
3. Software and supply-chain worlds validate through the same `World` contract.
4. The same graph loader can load either world without domain-specific logic.


## Verification

The M2 unit/contract suite is independent of a running FalkorDB instance:

```bash
uv run pytest -m "not integration"
```

The integration suite exercises the same loader against FalkorDB:

```bash
uv run pytest -m integration
```

The standalone M2 contract check validates both domain worlds without requiring
FalkorDB:

```bash
uv run python scripts/m2_check.py
```
