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


## M3 — Software investigation world

M3 replaces the minimal software example with a controlled investigation
scenario designed to make graph reasoning non-trivial.

The software world contains:

- a six-node ground-truth path from commit to incident,
- a temporally valid infrastructure alternative with missing evidence,
- a configuration alternative that occurs after the incident,
- unrelated graph distractors,
- source records for the evidence-backed path,
- temporal metadata on relevant events and relationships.

The intended question is:

> Why did `incident-001` happen?

Run the M3 gate against FalkorDB:

```bash
uv run python scripts/m3_check.py
```

M3 deliberately does not implement investigator reasoning. It creates the
controlled world required for M6-M11, where traversal, temporal validation,
evidence validation, and hypothesis competition are implemented.


## M4 — Provenance

M4 makes graph relationships auditable before the investigation engine is
built.

Relationships now have stable identity and explicit provenance fields:

- `edge_id`
- `evidence_status`
- `evidence_source_ids`
- temporal metadata
- `provenance_version`

Source records expose:

- `record`
- `span`
- `observed_at`
- `status`

The provenance resolver returns the relationship together with its resolved
source evidence. Missing evidence is represented explicitly as
`evidence_status=UNKNOWN`; the system does not manufacture support.

Run the M4 gate against FalkorDB:

```bash
uv run python scripts/m4_check.py
```

Expected:

```text
M4 provenance check
relationship_identity=PASS edges=17
source_records=PASS sources=5
primary_path_provenance=PASS
missing_evidence_explicit=PASS
M4_STATUS=PASS
```

Run the full non-integration suite:

```bash
uv run pytest -m "not integration"
```

M4 still does not implement temporal path filtering, hypothesis competition,
agentic investigation, or LLM synthesis. Those remain later milestones.
