# FalkorDB Capabilities

Status: M0

## Why FalkorDB

FalkorDB is the graph substrate for Continuum. The V1 architecture requires
graph operations to be computationally necessary, rather than using the graph
as decorative context around ordinary vector retrieval.

## Relevant Capabilities

### Property Graph Model

FalkorDB supports nodes, relationships, labels and properties. This maps
naturally to Continuum's core objects:

- Entity
- Event
- Change
- Observation
- Outcome
- Source

### Cypher

FalkorDB supports OpenCypher with proprietary extensions.

Continuum can therefore express investigation primitives as graph queries
rather than encoding all relationships into application-side Python logic.

Initial operations to validate in M1:

- locate an entity or outcome
- expand neighbors
- match relationship patterns
- find paths
- filter by properties
- filter by temporal properties
- collect source/provenance metadata

### Path Representation

FalkorDB supports path variables in Cypher. This is directly relevant to
multi-hop investigation because an explanation can be represented as an
ordered graph path rather than a bag of retrieved documents.

### Temporal Data

FalkorDB supports temporal data types including Date, DateTime, LocalDateTime,
Time, LocalTime and Duration.

Continuum will initially store investigation timestamps as graph properties
and implement only the temporal operations required by V1.

### Indexing and Search

FalkorDB provides range, full-text and vector indexing.

These capabilities are useful for locating investigation seeds, but they do
not replace traversal. Search finds candidates; graph structure determines
how candidates connect.

### Graph Algorithms

FalkorDB exposes graph algorithms and traversal-oriented functionality. M1
should experimentally determine which built-in operations are useful before
building custom traversal code.

### Python Connectivity

FalkorDB provides an official Python client. The current foundation therefore
uses a small GraphClient wrapper so the rest of Continuum is not coupled to
connection setup details.

## Planned M1 Graph Experiments

1. Create a minimal graph.
2. Create typed nodes and relationships.
3. Query one-hop neighbors.
4. Query a multi-hop path.
5. Apply timestamp filters.
6. Retrieve relationship/source properties.
7. Test path ranking inputs.
8. Confirm repeatable local Docker startup.

## Important Boundary

GraphRAG-SDK is available and may be used where it materially helps ingestion
or graph construction. It must not become the definition of the investigator.

The core V1 flow remains:

Question
→ Investigator
→ FalkorDB traversal
→ Candidate explanations
→ Validation
→ LLM synthesis

## M1 Gate

Without an LLM, Continuum must be able to answer questions such as:

- What is connected to X?
- What paths connect X and Y?
- What happened before X?
- What evidence supports relationship R?

If FalkorDB cannot provide useful investigation primitives, stop and redesign
before adding agentic behavior.
