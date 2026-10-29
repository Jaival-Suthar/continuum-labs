# Prior Art Research

Status: M0 / Commit 1

## Purpose

Establish what already exists around graph-based retrieval, operational diagnosis,
and graph-backed AI investigation before implementation.

## 1. GraphRAG

Microsoft Research describes GraphRAG as combining text extraction, network
analysis, and LLM prompting/summarization to improve understanding of private
narrative datasets.

Continuum overlaps with GraphRAG in using graphs to expose relationships that
ordinary retrieval can miss.

The important distinction for this project is that Continuum is not defined as
a document-retrieval technique. Its research target is an investigation loop:
locate a target, traverse relationships, discover candidate paths, apply
temporal constraints, collect evidence, validate competing explanations, and
then synthesize a conclusion.

## 2. FalkorDB GraphRAG

FalkorDB's GraphRAG-SDK already provides schema-guided extraction, hybrid
retrieval, relationship expansion, cited answers, and incremental graph
updates.

Continuum should therefore not claim that graph-grounded retrieval or cited
GraphRAG is novel by itself.

The research opportunity is to make graph traversal and validation explicit
investigation operations, with a reusable investigator separated from the
domain ontology.

## 3. Operational Root-Cause Systems

Amazon DevOps Guru analyzes operational metrics and events, detects anomalous
behavior, and produces insights containing related metrics, events and
recommendations.

This establishes that operational diagnosis and correlation across telemetry
are already mature product categories.

Continuum should not claim to have invented operational RCA. Its software
world is a test environment for the more general investigation mechanism.

## 4. Code / Dependency Graphs

Graph-based code analysis can represent modules, functions and dependencies
as a queryable graph. This demonstrates the practical value of multi-hop
relationship traversal for software analysis.

Continuum uses this kind of connected software world as one domain, but does
not make the investigator itself software-specific.

## 5. Research Gap / Opportunity

The relevant gap for Continuum is architectural rather than claiming a new
database primitive:

> Can a reusable graph investigation mechanism reconstruct
> evidence-supported multi-hop explanations across different domains
> without rebuilding the reasoning engine for each domain?

That question motivates the M1-M16 implementation sequence.

## What We Explicitly Do Not Claim

- We did not invent GraphRAG.
- We did not invent graph traversal.
- We did not invent operational root-cause analysis.
- We do not claim graphs prove causality.
- We do not claim FalkorDB itself is novel technology created by Continuum.

## Sources

- Microsoft Research — Project GraphRAG
- FalkorDB Documentation — GraphRAG-SDK
- FalkorDB Documentation — Cypher
- Amazon Web Services — Amazon DevOps Guru
- FalkorDB — CodeGraph
