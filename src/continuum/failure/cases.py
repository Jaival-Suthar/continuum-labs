from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from continuum.core import EvidenceStatus, GraphEdge, GraphNode, World
from continuum.core.ontology import Ontology
from continuum.failure.model import FailureCase, FailureType
from continuum.validation import Claim

M14_ONTOLOGY = Ontology(name="m14-failure-suite")


@dataclass(frozen=True)
class _Data:
    _nodes: tuple[GraphNode, ...]
    _edges: tuple[GraphEdge, ...]

    def nodes(self) -> tuple[GraphNode, ...]:
        return self._nodes

    def edges(self) -> tuple[GraphEdge, ...]:
        return self._edges


def _node(
    node_id: str,
    label: str,
    name: str,
    timestamp: datetime | None,
    **properties: object,
) -> GraphNode:
    return GraphNode(
        id=node_id,
        label=label,
        name=name,
        timestamp=timestamp,
        properties={"m14": True, **properties},
    )


def _edge(
    source: str,
    relationship: str,
    target: str,
    *,
    edge_id: str,
    timestamp: datetime | None,
    evidence_source_ids: tuple[str, ...] = (),
    **properties: object,
) -> GraphEdge:
    return GraphEdge(
        source,
        relationship,
        target,
        timestamp=timestamp,
        evidence_source_ids=evidence_source_ids,
        edge_id=edge_id,
        properties={"m14": True, **properties},
    )


def _source(
    source_id: str,
    name: str,
    *,
    observed_at: datetime,
    record: str,
    status: str = EvidenceStatus.OBSERVED,
) -> GraphNode:
    return _node(
        source_id,
        "Source",
        name,
        None,
        observed_at=observed_at.isoformat(),
        record=record,
        status=status,
    )


def _world(
    name: str,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
) -> World:
    world = World(
        name=name, ontology=M14_ONTOLOGY, data=_Data(tuple(nodes), tuple(edges))
    )
    world.validate()
    return world


def missing_evidence_case() -> FailureCase:
    t0 = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    nodes = [
        _node("m14-missing-change", "Change", "Dependency update X", t0),
        _node(
            "m14-missing-service",
            "Entity",
            "Payments service",
            t0 + timedelta(minutes=10),
        ),
        _node(
            "m14-missing-incident",
            "Outcome",
            "Incident M14 missing evidence",
            t0 + timedelta(minutes=20),
        ),
        _source(
            "m14-missing-source-1",
            "Deployment record",
            observed_at=t0 + timedelta(minutes=10),
            record="m14-missing-edge-1",
        ),
    ]
    edges = [
        _edge(
            "m14-missing-change",
            "AFFECTS",
            "m14-missing-service",
            edge_id="m14-missing-edge-1",
            timestamp=t0,
            evidence_source_ids=("m14-missing-source-1",),
        ),
        _edge(
            "m14-missing-service",
            "RESULTED_IN",
            "m14-missing-incident",
            edge_id="m14-missing-edge-2",
            timestamp=t0 + timedelta(minutes=10),
        ),
    ]
    return FailureCase(
        case_id="m14-missing-evidence",
        domain="software",
        failure_type=FailureType.MISSING_EVIDENCE,
        world=_world("m14-missing-evidence", nodes, edges),
        question="Why did m14-missing-incident happen?",
        expected_behavior="Insufficient evidence.",
        expected_evidence_state="gap",
        expected_path_state="plausible_but_incomplete",
        expected_hypothesis_state="insufficient",
        metadata={"missing_edge_id": "m14-missing-edge-2"},
    )


def multiple_plausible_paths_case() -> FailureCase:
    t0 = datetime(2026, 9, 1, 11, 0, tzinfo=UTC)
    nodes = [
        _node("m14-multi-config", "Change", "Configuration change", t0),
        _node(
            "m14-multi-config-service",
            "Entity",
            "Configuration service",
            t0 + timedelta(minutes=10),
        ),
        _node("m14-multi-dependency", "Change", "Dependency change", t0),
        _node(
            "m14-multi-dependency-service",
            "Entity",
            "Dependency service",
            t0 + timedelta(minutes=10),
        ),
        _node(
            "m14-multi-incident",
            "Outcome",
            "Incident M14 multiple paths",
            t0 + timedelta(minutes=20),
        ),
    ]
    edges = [
        _edge(
            "m14-multi-config",
            "CHANGED",
            "m14-multi-config-service",
            edge_id="m14-multi-edge-1",
            timestamp=t0,
            evidence_source_ids=("m14-multi-source-1",),
        ),
        _edge(
            "m14-multi-config-service",
            "RESULTED_IN",
            "m14-multi-incident",
            edge_id="m14-multi-edge-2",
            timestamp=t0 + timedelta(minutes=10),
            evidence_source_ids=("m14-multi-source-2",),
        ),
        _edge(
            "m14-multi-dependency",
            "CHANGED",
            "m14-multi-dependency-service",
            edge_id="m14-multi-edge-3",
            timestamp=t0,
            evidence_source_ids=("m14-multi-source-3",),
        ),
        _edge(
            "m14-multi-dependency-service",
            "RESULTED_IN",
            "m14-multi-incident",
            edge_id="m14-multi-edge-4",
            timestamp=t0 + timedelta(minutes=10),
            evidence_source_ids=("m14-multi-source-4",),
        ),
    ]
    for index in range(1, 5):
        nodes.append(
            _source(
                f"m14-multi-source-{index}",
                f"Authoritative evidence {index}",
                observed_at=t0 + timedelta(minutes=10),
                record=f"m14-multi-edge-{index}",
            )
        )
    return FailureCase(
        case_id="m14-multiple-plausible-paths",
        domain="software",
        failure_type=FailureType.MULTIPLE_PLAUSIBLE_PATHS,
        world=_world("m14-multiple-plausible-paths", nodes, edges),
        question="Why did m14-multi-incident happen?",
        expected_behavior="Multiple explanations remain plausible.",
        expected_evidence_state="supported",
        expected_path_state="multiple_valid",
        expected_hypothesis_state="ambiguous",
    )


def temporal_contradiction_case() -> FailureCase:
    incident_time = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    cause_time = incident_time + timedelta(minutes=10)
    nodes = [
        _node("m14-temporal-cause", "Change", "Deployment after incident", cause_time),
        _node("m14-temporal-service", "Entity", "Payments service", cause_time),
        _node(
            "m14-temporal-incident",
            "Outcome",
            "Incident M14 temporal contradiction",
            incident_time,
        ),
        _source(
            "m14-temporal-source-1",
            "Deployment record",
            observed_at=cause_time,
            record="m14-temporal-edge-1",
        ),
        _source(
            "m14-temporal-source-2",
            "Incident record",
            observed_at=incident_time,
            record="m14-temporal-edge-2",
        ),
    ]
    edges = [
        _edge(
            "m14-temporal-cause",
            "AFFECTS",
            "m14-temporal-service",
            edge_id="m14-temporal-edge-1",
            timestamp=cause_time,
            evidence_source_ids=("m14-temporal-source-1",),
        ),
        _edge(
            "m14-temporal-service",
            "RESULTED_IN",
            "m14-temporal-incident",
            edge_id="m14-temporal-edge-2",
            timestamp=cause_time,
            evidence_source_ids=("m14-temporal-source-2",),
        ),
    ]
    return FailureCase(
        case_id="m14-temporal-contradiction",
        domain="software",
        failure_type=FailureType.TEMPORAL_CONTRADICTION,
        world=_world("m14-temporal-contradiction", nodes, edges),
        question="Why did m14-temporal-incident happen?",
        expected_behavior="Path rejected.",
        expected_evidence_state="contradicted",
        expected_path_state="invalid",
        expected_hypothesis_state="rejected",
        metadata={
            "effect_time": incident_time.isoformat(),
            "cause_time": cause_time.isoformat(),
        },
    )


def misleading_document_case() -> FailureCase:
    t0 = datetime(2026, 9, 1, 13, 0, tzinfo=UTC)
    nodes = [
        _node("m14-misleading-real-cause", "Change", "Configuration change Y", t0),
        _node(
            "m14-misleading-service",
            "Entity",
            "Payments service",
            t0 + timedelta(minutes=10),
        ),
        _node(
            "m14-misleading-incident",
            "Outcome",
            "Incident M14 misleading document",
            t0 + timedelta(minutes=20),
        ),
        _node(
            "m14-misleading-deployment",
            "Change",
            "Deployment X",
            t0 - timedelta(minutes=5),
        ),
        _source(
            "m14-misleading-authoritative",
            "Authoritative configuration record",
            observed_at=t0,
            record="m14-misleading-edge-1",
        ),
        _source(
            "m14-misleading-document",
            (
                "Misleading incident report: Deployment X caused the service failure; "
                "this statement is not represented as a graph relationship."
            ),
            observed_at=t0 + timedelta(minutes=25),
            record="misleading-document-1",
        ),
    ]
    edges = [
        _edge(
            "m14-misleading-real-cause",
            "CHANGED",
            "m14-misleading-service",
            edge_id="m14-misleading-edge-1",
            timestamp=t0,
            evidence_source_ids=("m14-misleading-authoritative",),
        ),
        _edge(
            "m14-misleading-service",
            "RESULTED_IN",
            "m14-misleading-incident",
            edge_id="m14-misleading-edge-2",
            timestamp=t0 + timedelta(minutes=10),
            evidence_source_ids=("m14-misleading-authoritative",),
        ),
    ]
    return FailureCase(
        case_id="m14-misleading-document",
        domain="software",
        failure_type=FailureType.MISLEADING_DOCUMENT,
        world=_world("m14-misleading-document", nodes, edges),
        question="Why did m14-misleading-incident happen?",
        expected_behavior="Unsupported relationship rejected.",
        expected_evidence_state="unsupported",
        expected_path_state="no_graph_relationship",
        expected_hypothesis_state="unsupported",
        probe_claim=Claim(
            "m14-misleading-deployment",
            "RESULTED_IN",
            "m14-misleading-incident",
        ),
        retrieval_query="Deployment X caused the service failure",
        expected_retrieved_document_id="node:m14-misleading-document",
    )


def all_failure_cases() -> tuple[FailureCase, ...]:
    return (
        missing_evidence_case(),
        multiple_plausible_paths_case(),
        temporal_contradiction_case(),
        misleading_document_case(),
    )


def failure_cases_by_type(failure_type: str) -> tuple[FailureCase, ...]:
    cases = all_failure_cases()
    if failure_type not in FailureType.ALL:
        raise ValueError(f"Unsupported M14 failure type: {failure_type}")
    return tuple(case for case in cases if case.failure_type == failure_type)
