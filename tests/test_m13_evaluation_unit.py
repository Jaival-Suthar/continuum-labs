from __future__ import annotations

from datetime import UTC, datetime

from continuum.evaluation import aggregate, build_evaluation_dataset
from continuum.evaluation.metrics import (
    evidence_metrics,
    path_recovery,
    temporal_metrics,
)
from continuum.evaluation.model import EvaluationResult, PathRecoveryMetrics


def test_each_domain_has_exactly_20_independent_controlled_cases():
    software = build_evaluation_dataset("software")
    supply = build_evaluation_dataset("supply-chain")

    assert len(software.cases) == 20
    assert len(supply.cases) == 20
    assert len({case.case_id for case in software.cases}) == 20
    assert len({case.case_id for case in supply.cases}) == 20
    assert all(case.ground_truth_edge_ids for case in software.cases)
    assert all(case.ground_truth_edge_ids for case in supply.cases)
    assert all(case.expected_answer for case in software.cases)
    assert all(case.expected_answer for case in supply.cases)


def test_every_ground_truth_edge_and_evidence_reference_exists_in_its_world():
    for dataset in (
        build_evaluation_dataset("software"),
        build_evaluation_dataset("supply-chain"),
    ):
        edges = {edge.stable_id: edge for edge in dataset.world.data.edges()}
        nodes = {node.id for node in dataset.world.data.nodes()}
        for case in dataset.cases:
            assert all(node_id in nodes for node_id in case.ground_truth_path)
            assert all(edge_id in edges for edge_id in case.ground_truth_edge_ids)
            for edge_id, source_ids in case.expected_edge_evidence.items():
                assert set(source_ids) <= set(edges[edge_id].evidence_source_ids)


def test_ground_truth_is_independent_and_persistable(tmp_path):
    case = build_evaluation_dataset("software").cases[0]
    path = case.write_json(tmp_path / "case.json")
    payload = path.read_text(encoding="utf-8")

    assert "ground_truth_path" in payload
    assert "expected_answer" in payload
    assert "distractor_paths" in payload
    assert "Continuum" not in payload


def test_path_recovery_reports_exact_and_partial_recovery():
    gt = ("a", "b", "c", "d")
    metrics = path_recovery(gt, (("a", "b", "x", "d"), ("a", "b", "c", "d")))

    assert metrics.exact_match is True
    assert metrics.edge_recall == 1.0
    assert metrics.node_recall == 1.0
    assert metrics.best_recovered_path == gt


def test_evidence_metrics_are_deterministic_and_do_not_infer_support():
    metrics = evidence_metrics(
        {"e1": ("s1",), "e2": ("s2",)},
        ("e1", "e2", "e3"),
        {"e1": ("s1",), "e2": (), "e3": ("unrelated",)},
    )

    assert metrics.claims_evaluated == 3
    assert metrics.supported_claims == 2
    assert metrics.unsupported_claims == 1
    assert metrics.coverage == 2 / 3
    assert metrics.unsupported_claim_rate == 1 / 3


def test_temporal_metrics_use_explicit_timestamp_order_only():
    a = datetime(2026, 8, 1, 9, tzinfo=UTC)
    b = datetime(2026, 8, 1, 10, tzinfo=UTC)
    constraints = (
        __import__(
            "continuum.evaluation.model", fromlist=["TemporalConstraint"]
        ).TemporalConstraint("a", "b"),
    )

    assert (
        temporal_metrics(constraints, {"a": a, "b": b}, ("a", "b")).consistent is True
    )
    assert (
        temporal_metrics(constraints, {"a": b, "b": a}, ("a", "b")).consistent is False
    )


def test_aggregate_uses_executed_result_values():
    path = PathRecoveryMetrics(True, 1.0, 1.0, 1.0, 1.0, ("a", "b"))
    evidence = evidence_metrics({"e1": ("s1",)}, ("e1",), {"e1": ("s1",)})
    from continuum.evaluation.model import (
        BaselineCaseResult,
        ContinuumCaseResult,
        EfficiencyMetrics,
        TemporalConstraint,
        TemporalMetrics,
    )

    baseline = BaselineCaseResult(
        (), (), (), (), None, None, path, evidence, TemporalMetrics(1, 1, True, True)
    )
    continuum = ContinuumCaseResult(
        "b",
        (("a", "b"),),
        ("s1",),
        path,
        evidence,
        TemporalMetrics(1, 1, True, True),
        EfficiencyMetrics(3, 3, 0, 2, 2, 1, 1.5),
        ("x",),
    )
    result = EvaluationResult(
        "software-001",
        "software",
        "q",
        ("a", "b"),
        ("e1",),
        baseline,
        continuum,
        (TemporalConstraint("a", "b"),),
        "answer",
    )

    summary = aggregate((result,), system="continuum")
    assert summary.cases == 1
    assert summary.exact_path_match_rate == 1.0
    assert summary.evidence_coverage == 1.0
    assert summary.mean_graph_operations == 3.0
