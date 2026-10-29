# Continuum

General-purpose graph investigation engine.

## V1 foundation

- FalkorDB-backed graph investigation
- Domain-independent investigation core
- Evidence and provenance
- Temporal validation
- Software and supply-chain worlds

## M1 — FalkorDB foundation

Start FalkorDB:

```bash
docker compose up -d
```

Check connectivity:

```bash
python scripts/check_falkordb.py
```

Run unit tests:

```bash
pytest -m "not integration"
```

Run the FalkorDB integration check:

```bash
pytest -m integration
```

M1 deliberately establishes the graph infrastructure before introducing an
LLM or agent. The graph must be able to perform investigation work directly.


## M2 — Universal core model

M2 defines the domain-independent semantic contract used by Continuum.

Core objects:

- `Entity`
- `Event`
- `Change`
- `Observation`
- `Outcome`
- `Source`

Core relationships:

- `AFFECTS`
- `DEPENDS_ON`
- `CHANGED`
- `PRECEDED`
- `RESULTED_IN`
- `OBSERVED_AS`
- `SUPPORTED_BY`
- `MENTIONED_IN`
- `OWNED_BY`

A `World` supplies an ontology, data adapter, and temporal model. The
investigator and graph loader consume that contract without branching on the
domain. Software and supply-chain packages demonstrate two different worlds
using the same universal core.

Validate the M2 contract without FalkorDB:

```bash
uv run pytest -m "not integration"
```

Validate both domain packages against FalkorDB:

```bash
uv run python scripts/m2_check.py
uv run pytest -m integration
```
