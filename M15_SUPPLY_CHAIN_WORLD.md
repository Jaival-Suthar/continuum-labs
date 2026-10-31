# M15 — Supply-Chain World

## Objective

Prove domain transfer without adding supply-chain logic to the investigation engine.

The world is:

```text
Supplier → Component → Factory → Shipment → Warehouse → Customer → Impact
```

The investigation question is:

> Why was Customer X affected?

## Architecture gate

M15 keeps `src/continuum/investigator/engine.py` unchanged. The supply-chain package supplies the ontology, schema, world data adapter, and deterministic dataset. The universal `WorldLoader`, graph layer, temporal validation, evidence validation, investigation state, and hypothesis competition remain shared.

## Dataset

The fixture contains:

- a six-hop fully evidenced primary explanation;
- an independent six-hop alternative explanation sharing the downstream warehouse/customer/impact;
- a temporally contradictory upstream chain that must be rejected;
- disconnected distractor entities;
- independent observed provenance records so no single source contains the whole explanation.

The Customer entity intentionally uses the internal identifier `account-001` while its display name is `Customer X`. This preserves the natural-language question lookup behavior of the existing domain-independent investigator without changing that investigator.

## Verification

Unit checks:

```text
PYTHONPATH=src:. pytest -q -m "not integration"
```

M15 live gate, with FalkorDB running:

```text
PYTHONPATH=src:. python scripts/m15_check.py
```

The live gate loads the world through the universal loader, asks the unchanged `Investigator` the Customer X question, verifies valid and invalid paths, resolves evidence, and exercises M10 hypothesis competition.
