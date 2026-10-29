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
