from __future__ import annotations

from collections.abc import Iterable
from itertools import pairwise

from continuum.core.models import InvestigationPath
from continuum.evaluation.model import (
    EfficiencyMetrics,
    EvidenceMetrics,
    PathRecoveryMetrics,
    TemporalConstraint,
    TemporalMetrics,
)


def _edge_keys_from_path(path: tuple[str, ...]) -> set[tuple[str, str]]:
    return set(pairwise(path))


def path_recovery(
    ground_truth_path: tuple[str, ...],
    recovered_paths: Iterable[tuple[str, ...]],
) -> PathRecoveryMetrics:
    """Compute exact and set-based path recovery without an LLM judge."""
    candidates = tuple(recovered_paths)
    gt_nodes = set(ground_truth_path)
    gt_edges = _edge_keys_from_path(ground_truth_path)

    exact = next((path for path in candidates if path == ground_truth_path), None)

    best = ()
    best_key = (-1.0, -1.0, -1.0, ())
    for path in candidates:
        nodes = set(path)
        edges = _edge_keys_from_path(path)
        node_recall = len(nodes & gt_nodes) / len(gt_nodes) if gt_nodes else 1.0
        edge_precision = len(edges & gt_edges) / len(edges) if edges else 0.0
        edge_recall = len(edges & gt_edges) / len(gt_edges) if gt_edges else 1.0
        key = (edge_recall, edge_precision, node_recall, tuple(path))
        if key > best_key:
            best_key = key
            best = path

    if exact is not None:
        best = exact

    nodes = set(best)
    edges = _edge_keys_from_path(best)
    return PathRecoveryMetrics(
        exact_match=exact is not None,
        node_precision=(len(nodes & gt_nodes) / len(nodes) if nodes else 0.0),
        node_recall=(len(nodes & gt_nodes) / len(gt_nodes) if gt_nodes else 1.0),
        edge_precision=(len(edges & gt_edges) / len(edges) if edges else 0.0),
        edge_recall=(len(edges & gt_edges) / len(gt_edges) if gt_edges else 1.0),
        best_recovered_path=tuple(best),
    )


def evidence_metrics(
    expected_edge_evidence: dict[str, tuple[str, ...]],
    claimed_edge_ids: Iterable[str],
    evidence_by_edge: dict[str, tuple[str, ...]],
) -> EvidenceMetrics:
    """Measure evidence coverage of explicitly asserted graph relationships."""
    claims = tuple(dict.fromkeys(claimed_edge_ids))
    if not claims:
        return EvidenceMetrics(0, 0, 0, 0.0, 0.0)

    supported = 0
    for edge_id in claims:
        expected = set(expected_edge_evidence.get(edge_id, ()))
        actual = set(evidence_by_edge.get(edge_id, ()))
        if expected and expected <= actual or not expected and actual:
            supported += 1

    unsupported = len(claims) - supported
    return EvidenceMetrics(
        claims_evaluated=len(claims),
        supported_claims=supported,
        unsupported_claims=unsupported,
        coverage=supported / len(claims),
        unsupported_claim_rate=unsupported / len(claims),
    )


def continuum_evidence_metrics(
    path: InvestigationPath | None,
    expected_edge_evidence: dict[str, tuple[str, ...]],
) -> EvidenceMetrics:
    if path is None:
        return EvidenceMetrics(0, 0, 0, 0.0, 0.0)
    edge_ids = tuple(edge_id for edge_id in path.edge_ids if edge_id is not None)
    evidence_by_edge: dict[str, tuple[str, ...]] = {}
    # The path's Evidence objects identify source records. For each path hop,
    # the deterministic engine has already counted whether provenance exists.
    # Assign all path evidence to each hop only when that hop is represented in
    # edge_records with matching source ids; otherwise missing evidence remains
    # unsupported rather than being guessed.
    for index, edge_id in enumerate(edge_ids):
        record = path.edge_records[index] if index < len(path.edge_records) else {}
        source_ids = tuple(record.get("evidence_source_ids") or ())
        evidence_by_edge[edge_id] = source_ids

    # If graph records omit the source list, fall back only to the explicit
    # path-level evidence IDs when the hop is known to have supporting evidence.
    if path.evidence and path.supporting_relationship_count == len(edge_ids):
        all_ids = tuple(item.source_id for item in path.evidence)
        for edge_id in edge_ids:
            evidence_by_edge.setdefault(edge_id, all_ids)

    return evidence_metrics(expected_edge_evidence, edge_ids, evidence_by_edge)


def temporal_metrics(
    constraints: tuple[TemporalConstraint, ...],
    node_timestamps: dict[str, object],
    path: tuple[str, ...] | None = None,
) -> TemporalMetrics:
    """Evaluate explicit before/after constraints from persisted timestamps."""
    path_valid: bool | None = None
    if path is not None:
        timestamps = [node_timestamps.get(node_id) for node_id in path]
        if all(timestamp is not None for timestamp in timestamps):
            path_valid = all(left <= right for left, right in pairwise(timestamps))
        else:
            path_valid = None

    if not constraints:
        return TemporalMetrics(0, 0, path_valid, path_valid is not False)

    satisfied = 0
    for constraint in constraints:
        left = node_timestamps.get(constraint.subject_id)
        right = node_timestamps.get(constraint.object_id)
        if left is None or right is None:
            continue
        if (
            constraint.relation == "before"
            and left <= right
            or constraint.relation == "after"
            and left >= right
        ):
            satisfied += 1

    constraints_consistent = satisfied == len(constraints)
    return TemporalMetrics(
        constraints_evaluated=len(constraints),
        constraints_satisfied=satisfied,
        path_valid=path_valid,
        consistent=constraints_consistent and path_valid is not False,
    )


def efficiency_metrics(
    *,
    graph_reads: int,
    graph_writes: int,
    investigation_steps: int,
    nodes_explored: int,
    edges_explored: int,
    elapsed_ms: float,
) -> EfficiencyMetrics:
    if (
        min(
            graph_reads,
            graph_writes,
            investigation_steps,
            nodes_explored,
            edges_explored,
        )
        < 0
    ):
        raise ValueError("efficiency counts must be >= 0")
    if elapsed_ms < 0:
        raise ValueError("elapsed_ms must be >= 0")
    return EfficiencyMetrics(
        graph_operations=graph_reads + graph_writes,
        graph_reads=graph_reads,
        graph_writes=graph_writes,
        investigation_steps=investigation_steps,
        nodes_explored=nodes_explored,
        edges_explored=edges_explored,
        elapsed_ms=elapsed_ms,
    )
