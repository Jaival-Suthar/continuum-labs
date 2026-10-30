from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from continuum.core.models import GraphEdge, GraphNode
from continuum.core.ontology import Ontology
from continuum.core.world import World
from continuum.evaluation.model import EvaluationCase, TemporalConstraint
from domains.software.ontology import SOFTWARE_ONTOLOGY
from domains.supply_chain.ontology import SUPPLY_CHAIN_ONTOLOGY


@dataclass(frozen=True)
class _Pattern:
    name: str
    labels: tuple[str, ...]
    relationships: tuple[str, ...]
    alternate_at: int | None = None
    missing_evidence_at: int | None = None


SOFTWARE_PATTERNS = (
    _Pattern(
        "dependency_chain",
        ("Commit", "Dependency", "Service", "Deployment", "Metric", "Incident"),
        ("CHANGED", "DEPENDS_ON", "AFFECTS", "AFFECTS", "RESULTED_IN"),
    ),
    _Pattern(
        "commit_service",
        ("Commit", "Service", "Deployment", "Incident"),
        ("CHANGED", "AFFECTS", "RESULTED_IN"),
        alternate_at=1,
    ),
    _Pattern(
        "dependency_incident",
        ("Commit", "Dependency", "Service", "Incident"),
        ("CHANGED", "DEPENDS_ON", "RESULTED_IN"),
    ),
    _Pattern(
        "config_path",
        ("Configuration", "Service", "Deployment", "Metric", "Incident"),
        ("CHANGED", "AFFECTS", "AFFECTS", "RESULTED_IN"),
        alternate_at=0,
    ),
    _Pattern(
        "infra_path",
        ("InfrastructureEvent", "Service", "Deployment", "Incident"),
        ("AFFECTS", "AFFECTS", "RESULTED_IN"),
        missing_evidence_at=0,
    ),
    _Pattern(
        "short_dependency",
        ("Commit", "Dependency", "Deployment", "Incident"),
        ("CHANGED", "AFFECTS", "RESULTED_IN"),
        alternate_at=1,
    ),
    _Pattern(
        "service_metric",
        ("Commit", "Service", "Metric", "Incident"),
        ("CHANGED", "AFFECTS", "RESULTED_IN"),
    ),
    _Pattern(
        "config_metric",
        ("Configuration", "Deployment", "Metric", "Incident"),
        ("CHANGED", "AFFECTS", "RESULTED_IN"),
        alternate_at=0,
    ),
    _Pattern(
        "long_service",
        ("Commit", "Dependency", "Service", "Deployment", "Metric", "Incident"),
        ("CHANGED", "DEPENDS_ON", "AFFECTS", "AFFECTS", "RESULTED_IN"),
        missing_evidence_at=1,
    ),
    _Pattern(
        "infra_metric",
        ("InfrastructureEvent", "Service", "Metric", "Incident"),
        ("AFFECTS", "AFFECTS", "RESULTED_IN"),
        alternate_at=0,
    ),
    _Pattern(
        "deployment_direct",
        ("Commit", "Service", "Deployment", "Incident"),
        ("CHANGED", "AFFECTS", "RESULTED_IN"),
    ),
    _Pattern(
        "dependency_metric",
        ("Commit", "Dependency", "Service", "Metric", "Incident"),
        ("CHANGED", "DEPENDS_ON", "AFFECTS", "RESULTED_IN"),
        alternate_at=2,
    ),
    _Pattern(
        "config_service",
        ("Configuration", "Service", "Incident"),
        ("CHANGED", "RESULTED_IN"),
        missing_evidence_at=0,
    ),
    _Pattern(
        "infra_deploy",
        ("InfrastructureEvent", "Deployment", "Metric", "Incident"),
        ("AFFECTS", "AFFECTS", "RESULTED_IN"),
        alternate_at=1,
    ),
    _Pattern(
        "commit_metric", ("Commit", "Metric", "Incident"), ("CHANGED", "RESULTED_IN")
    ),
    _Pattern(
        "dependency_deploy",
        ("Commit", "Dependency", "Deployment", "Metric", "Incident"),
        ("CHANGED", "DEPENDS_ON", "AFFECTS", "RESULTED_IN"),
        missing_evidence_at=2,
    ),
    _Pattern(
        "config_deploy",
        ("Configuration", "Deployment", "Incident"),
        ("CHANGED", "RESULTED_IN"),
        alternate_at=0,
    ),
    _Pattern(
        "infra_service_metric",
        ("InfrastructureEvent", "Service", "Deployment", "Metric", "Incident"),
        ("AFFECTS", "AFFECTS", "AFFECTS", "RESULTED_IN"),
        missing_evidence_at=1,
    ),
    _Pattern(
        "commit_service_metric",
        ("Commit", "Service", "Deployment", "Metric", "Incident"),
        ("CHANGED", "AFFECTS", "AFFECTS", "RESULTED_IN"),
        alternate_at=2,
    ),
    _Pattern(
        "dependency_service",
        ("Commit", "Dependency", "Service", "Incident"),
        ("CHANGED", "DEPENDS_ON", "RESULTED_IN"),
        missing_evidence_at=1,
    ),
)

SUPPLY_PATTERNS = (
    _Pattern(
        "full_chain",
        (
            "Supplier",
            "Component",
            "Factory",
            "Shipment",
            "Warehouse",
            "Customer",
            "Impact",
        ),
        ("OWNED_BY", "DEPENDS_ON", "AFFECTS", "AFFECTS", "AFFECTS", "RESULTED_IN"),
    ),
    _Pattern(
        "shipment_chain",
        ("Supplier", "Component", "Factory", "Shipment", "Customer", "Impact"),
        ("OWNED_BY", "DEPENDS_ON", "AFFECTS", "AFFECTS", "RESULTED_IN"),
        alternate_at=2,
    ),
    _Pattern(
        "warehouse_chain",
        ("Supplier", "Component", "Shipment", "Warehouse", "Customer", "Impact"),
        ("OWNED_BY", "AFFECTS", "AFFECTS", "AFFECTS", "RESULTED_IN"),
    ),
    _Pattern(
        "factory_chain",
        ("Component", "Factory", "Shipment", "Warehouse", "Customer", "Impact"),
        ("DEPENDS_ON", "AFFECTS", "AFFECTS", "AFFECTS", "RESULTED_IN"),
        missing_evidence_at=1,
    ),
    _Pattern(
        "supplier_factory",
        ("Supplier", "Factory", "Shipment", "Warehouse", "Customer", "Impact"),
        ("OWNED_BY", "AFFECTS", "AFFECTS", "AFFECTS", "RESULTED_IN"),
        alternate_at=1,
    ),
    _Pattern(
        "supplier_warehouse",
        ("Supplier", "Component", "Factory", "Warehouse", "Customer", "Impact"),
        ("OWNED_BY", "DEPENDS_ON", "AFFECTS", "AFFECTS", "RESULTED_IN"),
    ),
    _Pattern(
        "shipment_impact",
        ("Supplier", "Component", "Factory", "Shipment", "Impact"),
        ("OWNED_BY", "DEPENDS_ON", "AFFECTS", "RESULTED_IN"),
        alternate_at=1,
    ),
    _Pattern(
        "component_customer",
        ("Supplier", "Component", "Warehouse", "Customer", "Impact"),
        ("OWNED_BY", "AFFECTS", "AFFECTS", "RESULTED_IN"),
        missing_evidence_at=1,
    ),
    _Pattern(
        "factory_customer",
        ("Factory", "Shipment", "Warehouse", "Customer", "Impact"),
        ("AFFECTS", "AFFECTS", "AFFECTS", "RESULTED_IN"),
    ),
    _Pattern(
        "supplier_shipment",
        ("Supplier", "Component", "Factory", "Shipment", "Impact"),
        ("OWNED_BY", "DEPENDS_ON", "AFFECTS", "RESULTED_IN"),
        missing_evidence_at=2,
    ),
    _Pattern(
        "component_factory",
        ("Supplier", "Component", "Factory", "Customer", "Impact"),
        ("OWNED_BY", "DEPENDS_ON", "AFFECTS", "RESULTED_IN"),
        alternate_at=1,
    ),
    _Pattern(
        "shipment_customer",
        ("Shipment", "Warehouse", "Customer", "Impact"),
        ("AFFECTS", "AFFECTS", "RESULTED_IN"),
    ),
    _Pattern(
        "component_warehouse",
        ("Supplier", "Component", "Warehouse", "Impact"),
        ("OWNED_BY", "AFFECTS", "RESULTED_IN"),
        missing_evidence_at=0,
    ),
    _Pattern(
        "factory_impact",
        ("Factory", "Shipment", "Customer", "Impact"),
        ("AFFECTS", "AFFECTS", "RESULTED_IN"),
        alternate_at=0,
    ),
    _Pattern(
        "supplier_customer",
        ("Supplier", "Component", "Customer", "Impact"),
        ("OWNED_BY", "AFFECTS", "RESULTED_IN"),
    ),
    _Pattern(
        "component_impact",
        ("Component", "Factory", "Shipment", "Impact"),
        ("DEPENDS_ON", "AFFECTS", "RESULTED_IN"),
        alternate_at=1,
    ),
    _Pattern(
        "warehouse_impact",
        ("Warehouse", "Customer", "Impact"),
        ("AFFECTS", "RESULTED_IN"),
    ),
    _Pattern(
        "supplier_impact",
        ("Supplier", "Factory", "Customer", "Impact"),
        ("OWNED_BY", "AFFECTS", "RESULTED_IN"),
        missing_evidence_at=1,
    ),
    _Pattern(
        "factory_warehouse",
        ("Supplier", "Component", "Factory", "Warehouse", "Impact"),
        ("OWNED_BY", "DEPENDS_ON", "AFFECTS", "RESULTED_IN"),
        alternate_at=2,
    ),
    _Pattern(
        "full_chain_gap",
        (
            "Supplier",
            "Component",
            "Factory",
            "Shipment",
            "Warehouse",
            "Customer",
            "Impact",
        ),
        ("OWNED_BY", "DEPENDS_ON", "AFFECTS", "AFFECTS", "AFFECTS", "RESULTED_IN"),
        missing_evidence_at=3,
    ),
)


def _timestamps(start: datetime, count: int) -> tuple[datetime, ...]:
    return tuple(start + timedelta(minutes=index * 10) for index in range(count))


def _source_id(case_number: int, hop: int) -> str:
    return f"source-{case_number:03d}-{hop:02d}"


def _build_case(
    *,
    number: int,
    domain: str,
    pattern: _Pattern,
) -> tuple[EvaluationCase, tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    prefix = "sw" if domain == "software" else "sc"
    ontology: Ontology = (
        SOFTWARE_ONTOLOGY if domain == "software" else SUPPLY_CHAIN_ONTOLOGY
    )
    case_id = f"{domain}-{number:03d}"
    start = datetime(2026, 8, 1, tzinfo=UTC) + timedelta(days=number)
    times = _timestamps(start, len(pattern.labels))

    path_nodes: list[GraphNode] = []
    for index, label in enumerate(pattern.labels):
        node_id = f"{prefix}-{number:03d}-{index:02d}"
        if label == "Incident":
            name = f"Incident {number:03d}"
        elif label == "Impact":
            name = f"Customer impact {number:03d}"
        else:
            name = f"{label.lower()} {number:03d}-{index:02d}"
        path_nodes.append(
            GraphNode(
                node_id,
                label,
                name,
                timestamp=times[index],
                properties={
                    "evaluation_case": case_id,
                    "case_role": "ground_truth",
                },
            )
        )

    nodes: list[GraphNode] = list(path_nodes)
    extra_nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    gt_edge_ids: list[str] = []
    source_evidence: list[str] = []
    expected_edge_evidence: dict[str, tuple[str, ...]] = {}
    for hop, relationship in enumerate(pattern.relationships):
        source = path_nodes[hop].id
        target = path_nodes[hop + 1].id
        edge_id = f"edge-{case_id}-{hop:02d}"
        source_id = _source_id(number, hop)
        gt_edge_ids.append(edge_id)
        evidence_ids = () if pattern.missing_evidence_at == hop else (source_id,)
        if evidence_ids:
            source_evidence.append(source_id)
        if evidence_ids:
            expected_edge_evidence[edge_id] = evidence_ids
        edges.append(
            GraphEdge(
                source,
                relationship,
                target,
                timestamp=times[hop],
                evidence_source_ids=evidence_ids,
                edge_id=edge_id,
                properties={"evaluation_case": case_id, "role": "ground_truth"},
            )
        )
        if evidence_ids:
            extra_nodes.append(
                GraphNode(
                    source_id,
                    "Source",
                    f"source record {case_id} hop {hop}",
                    observed_at=times[hop],
                    properties={
                        "evaluation_case": case_id,
                        "status": "OBSERVED",
                        "record": edge_id,
                        "span": f"controlled evidence for {source} -> {target}",
                    },
                )
            )

    nodes.extend(extra_nodes)
    distractor_paths: list[tuple[str, ...]] = []
    # A structurally plausible alternative shares the final outcome and one
    # middle node, but is independently named and has no provenance. This is
    # controlled distractor data, not an investigator-generated ground truth.
    if pattern.alternate_at is not None:
        alt_index = pattern.alternate_at
        alt_nodes: list[str] = [nodes[alt_index].id]
        alt_label = pattern.labels[alt_index]
        alt_id = f"{prefix}-{number:03d}-alt-{alt_index:02d}"
        nodes.append(
            GraphNode(
                alt_id,
                alt_label,
                f"alternative {alt_label.lower()} {number:03d}",
                timestamp=times[max(0, alt_index - 1)],
                properties={"evaluation_case": case_id, "case_role": "distractor"},
            )
        )
        alt_nodes.append(alt_id)
        outcome_id = f"{prefix}-{number:03d}-{len(pattern.labels) - 1:02d}"
        alt_nodes = [alt_nodes[0], alt_id, outcome_id]
        distractor_paths.append(tuple(alt_nodes))
        edges.append(
            GraphEdge(
                alt_nodes[0],
                "AFFECTS",
                alt_id,
                timestamp=times[min(alt_index + 1, len(times) - 1)],
                properties={"evaluation_case": case_id, "role": "distractor"},
            )
        )
        edges.append(
            GraphEdge(
                alt_id,
                "AFFECTS",
                outcome_id,
                timestamp=(
                    times[min(alt_index + 1, len(times) - 1)]
                    if pattern.alternate_at == 0
                    else times[-1] + timedelta(minutes=5)
                ),
                properties={"evaluation_case": case_id, "role": "distractor"},
            )
        )

    # Explicit source nodes are not represented in the ground-truth path, but
    # they are part of the controlled evidence available to both systems.
    temporal_constraints = tuple(
        TemporalConstraint(path_nodes[index].id, path_nodes[index + 1].id, "before")
        for index in range(len(path_nodes) - 1)
    )

    outcome_id = f"{prefix}-{number:03d}-{len(pattern.labels) - 1:02d}"
    cause = path_nodes[0].name
    expected_answer = (
        f"{cause} is the declared initiating change/event in the controlled path "
        f"for {outcome_id}; the explanation follows the ground-truth relationships "
        "in temporal order."
    )
    question_noun = "incident" if domain == "software" else "impact"
    question = f"Why did {question_noun} {outcome_id} happen?"

    case = EvaluationCase(
        case_id=case_id,
        domain=domain,
        question=question,
        ground_truth_path=tuple(node.id for node in path_nodes),
        ground_truth_edge_ids=tuple(gt_edge_ids),
        distractor_paths=tuple(distractor_paths),
        source_evidence=tuple(source_evidence),
        temporal_constraints=temporal_constraints,
        expected_answer=expected_answer,
        expected_edge_evidence=expected_edge_evidence,
    )
    ontology.validate_label("Source")
    return case, tuple(nodes), tuple(edges)


@dataclass(frozen=True)
class EvaluationDataset:
    domain: str
    world: World
    cases: tuple[EvaluationCase, ...]


def build_evaluation_dataset(domain: str) -> EvaluationDataset:
    if domain not in {"software", "supply-chain"}:
        raise ValueError("domain must be software or supply-chain")
    patterns = SOFTWARE_PATTERNS if domain == "software" else SUPPLY_PATTERNS
    if len(patterns) != 20:
        raise AssertionError("M13 requires exactly 20 controlled cases per domain")
    ontology = SOFTWARE_ONTOLOGY if domain == "software" else SUPPLY_CHAIN_ONTOLOGY
    all_nodes: list[GraphNode] = []
    all_edges: list[GraphEdge] = []
    cases: list[EvaluationCase] = []
    for number, pattern in enumerate(patterns, start=1):
        case, nodes, edges = _build_case(number=number, domain=domain, pattern=pattern)
        cases.append(case)
        all_nodes.extend(nodes)
        all_edges.extend(edges)

    # World validation is the benchmark's first deterministic gate.
    class _Data:
        def nodes(self) -> tuple[GraphNode, ...]:
            return tuple(all_nodes)

        def edges(self) -> tuple[GraphEdge, ...]:
            return tuple(all_edges)

    world = World(name=domain, ontology=ontology, data=_Data())
    world.validate()
    return EvaluationDataset(domain, world, tuple(cases))


def all_evaluation_datasets() -> tuple[EvaluationDataset, EvaluationDataset]:
    return build_evaluation_dataset("software"), build_evaluation_dataset(
        "supply-chain"
    )
