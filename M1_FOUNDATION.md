# M1 Foundation Gate

The M1 foundation is intentionally deterministic and LLM-free.

## Demonstrated capabilities

- FalkorDB starts through Docker Compose.
- Python connects through the official FalkorDB client.
- Core graph labels and relationships are defined.
- A representative software graph can be seeded.
- Cypher performs node lookup and neighborhood traversal.
- Multi-hop paths can be recovered from FalkorDB.
- Temporal filtering can identify records preceding an outcome.
- Relationships can expose supporting source records.

## Gate

The foundation is ready for M2 only when these operations work against a real
FalkorDB instance:

```text
What is connected to X?
What paths connect X and Y?
What happened before X?
What evidence supports relationship R?
```

No LLM is involved in these checks. FalkorDB is doing the graph work directly.
