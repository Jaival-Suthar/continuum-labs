from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass

from continuum.evaluation.model import EvaluationResult


@dataclass(frozen=True)
class MetricAggregate:
    cases: int
    exact_path_matches: int
    exact_path_match_rate: float
    mean_node_precision: float
    mean_node_recall: float
    mean_edge_precision: float
    mean_edge_recall: float
    evidence_coverage: float
    unsupported_claim_rate: float
    temporal_consistency_rate: float
    mean_graph_operations: float
    mean_graph_reads: float
    mean_nodes_explored: float
    mean_edges_explored: float
    mean_investigation_steps: float
    mean_elapsed_ms: float

    def to_dict(self) -> dict:
        return asdict(self)


def aggregate(results: Iterable[EvaluationResult], *, system: str) -> MetricAggregate:
    items = tuple(results)
    if not items:
        raise ValueError("cannot aggregate zero evaluation results")
    if system not in {"baseline", "continuum"}:
        raise ValueError("system must be baseline or continuum")

    path = [getattr(item, system).path_recovery for item in items]
    evidence = [getattr(item, system).evidence for item in items]
    exact = sum(metric.exact_match for metric in path)
    total_claims = sum(metric.claims_evaluated for metric in evidence)
    supported_claims = sum(metric.supported_claims for metric in evidence)
    temporal_rate = sum(
        getattr(item, system).temporal.consistent for item in items
    ) / len(items)

    if system == "baseline":
        efficiency_values = [(0, 0, 0, 0, 0) for _ in items]
        elapsed = [0.0 for _ in items]
    else:
        efficiency_values = [
            (
                item.continuum.efficiency.graph_operations,
                item.continuum.efficiency.graph_reads,
                item.continuum.efficiency.nodes_explored,
                item.continuum.efficiency.edges_explored,
                item.continuum.efficiency.investigation_steps,
            )
            for item in items
        ]
        elapsed = [item.continuum.efficiency.elapsed_ms for item in items]

    return MetricAggregate(
        cases=len(items),
        exact_path_matches=exact,
        exact_path_match_rate=exact / len(items),
        mean_node_precision=sum(x.node_precision for x in path) / len(items),
        mean_node_recall=sum(x.node_recall for x in path) / len(items),
        mean_edge_precision=sum(x.edge_precision for x in path) / len(items),
        mean_edge_recall=sum(x.edge_recall for x in path) / len(items),
        evidence_coverage=(supported_claims / total_claims if total_claims else 0.0),
        unsupported_claim_rate=(
            (total_claims - supported_claims) / total_claims if total_claims else 0.0
        ),
        temporal_consistency_rate=temporal_rate,
        mean_graph_operations=sum(x[0] for x in efficiency_values) / len(items),
        mean_graph_reads=sum(x[1] for x in efficiency_values) / len(items),
        mean_nodes_explored=sum(x[2] for x in efficiency_values) / len(items),
        mean_edges_explored=sum(x[3] for x in efficiency_values) / len(items),
        mean_investigation_steps=sum(x[4] for x in efficiency_values) / len(items),
        mean_elapsed_ms=sum(elapsed) / len(items),
    )
