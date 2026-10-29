# M4 — Provenance

M4 makes meaningful graph relationships auditable without introducing an LLM or
investigation logic.

## Contract

Every persisted relationship now carries:

- `edge_id`: stable relationship identity
- `timestamp` / temporal metadata when supplied
- `evidence_status`
- `evidence_source_ids`
- `provenance_version`

Every `Source` node used by provenance carries:

- `record`
- `span`
- `observed_at`
- `status`

The provenance resolver follows the relationship's explicit
`evidence_source_ids` and returns an auditable `GraphRelationship` containing
resolved `Evidence` records.

## Stable relationship identity

`GraphEdge.stable_id` is deterministic when an explicit `edge_id` is not
provided. It hashes the relationship's semantic identity, temporal fields,
evidence source IDs, and properties.

The loader merges relationships using `edge_id`, not only
`source + relationship + target`. This preserves distinct relationship
occurrences between the same endpoints.

## Missing evidence

Missing evidence is explicit:

```text
evidence_status = UNKNOWN
evidence_source_ids = []
```

This is intentional. M4 does not manufacture evidence for hypotheses that do
not have a source record.

## Verification

With FalkorDB running:

```bash
uv run pytest -m "not integration"
uv run python scripts/m2_check.py
uv run python scripts/m3_check.py
uv run python scripts/m4_check.py
uv run pytest -m integration
```

Expected M4 gate:

```text
M4 provenance check
relationship_identity=PASS edges=17
source_records=PASS sources=5
primary_path_provenance=PASS
missing_evidence_explicit=PASS
M4_STATUS=PASS
```

The exact edge/source counts are tied to the current controlled software
dataset. If the dataset intentionally changes, the gate should be updated
rather than hiding the change.

M4 does not implement temporal path filtering, hypothesis ranking, agentic
investigation, or final reporting. Those remain later milestones.
