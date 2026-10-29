# Continuum Differentiation

Status: M0

## The Problem

Many important questions are not contained in one document or retrieval
result. The useful answer may require reconstructing a chain of entities,
events, changes, observations and outcomes.

Continuum is designed around that reconstruction.

## What Continuum Is

> Continuum is a general-purpose graph investigation engine that lets AI
> investigate connected worlds by tracing entities, events and changes through
> FalkorDB, reconstructing multi-hop evidence paths, validating explanations,
> and reporting what the evidence supports.

## What It Is Not

V1 is explicitly not:

- a generic GraphRAG chatbot
- an agent-memory product
- Kubernetes RCA software
- an AIOps platform
- a fraud product
- a security product
- a supply-chain product
- a causal inference engine
- a counterfactual simulator
- an autonomous remediation platform
- a multi-agent swarm

These boundaries prevent the implementation from becoming an unfocused
collection of features.

## The Core Differentiator

The individual components are established technologies:

- graph databases
- Cypher
- GraphRAG
- LLM agents
- provenance
- operational diagnosis
- graph traversal

The proposed differentiation is their organization around a reusable
investigation abstraction:

```text
             WORLD
               |
               v
         INVESTIGATOR
               |
               v
           FalkorDB
               |
        +------+------+
        |             |
     evidence       paths
        |             |
        +------+------+
               |
           validation
               |
            synthesis
```

The investigator must not contain branches such as:

```python
if software:
    investigate_software()

if supply_chain:
    investigate_supply_chain()
```

Instead, domain-specific information belongs to a world definition containing
ontology, schema, data and temporal model.

## The Generality Test

The strongest proof of the architecture is:

```text
SOFTWARE WORLD
      |
      v
 SAME INVESTIGATOR
      ^
      |
SUPPLY-CHAIN WORLD
```

The investigator should retain the same search, traversal, investigation
state, hypothesis, validation and reporting mechanisms.

Only the world changes.

## Evidence as a First-Class Boundary

Continuum separates:

- OBSERVED — directly supported by source data
- DERIVED — computed from graph structure
- SUPPORTED INFERENCE — not directly observed but supported by evidence
- CONTRADICTED — evidence conflicts with the explanation
- UNKNOWN — insufficient evidence

The system must be comfortable returning:

> Insufficient evidence.

This is a product property, not an error condition.

## FalkorDB's Role

FalkorDB is not merely a database behind a retrieval pipeline.

The graph must perform meaningful work:

- locate entities
- traverse relationships
- discover paths
- apply temporal constraints
- collect evidence
- compare connected structures

If removing FalkorDB leaves an ordinary vector-RAG application that produces
essentially the same investigation, V1 has failed its architectural test.

## Research Positioning

We should claim an experiment, not a universal breakthrough:

> Continuum tests whether a reusable graph investigation mechanism can
> reconstruct evidence-supported multi-hop explanations across different
> domains using the same investigation architecture.

That is narrower, defensible, and measurable.
