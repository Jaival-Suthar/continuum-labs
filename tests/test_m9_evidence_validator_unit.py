from __future__ import annotations

from continuum.core import EvidenceStatus
from continuum.validation import Claim, ClaimClassification, EvidenceValidator


class Result:
    def __init__(self, result_set):
        self.result_set = result_set


class FakeGraph:
    """Deterministic graph fixture representing FalkorDB responses."""

    def __init__(
        self, *, exists=True, evidence=True, contradiction=False, temporal="valid"
    ):
        self.exists = exists
        self.evidence = evidence
        self.contradiction = contradiction
        self.temporal = temporal
        self.calls: list[tuple[str, dict | None]] = []

    def read(self, cypher, params=None):
        self.calls.append((cypher, params))

        if "MATCH (source {id:$subject})-[r:" in cypher:
            if not self.exists:
                return Result([])
            status = (
                EvidenceStatus.CONTRADICTED
                if self.contradiction
                else EvidenceStatus.OBSERVED
            )
            return Result(
                [
                    [
                        "commit-001",
                        "CHANGED",
                        "dependency-001",
                        "edge-001",
                        "2026-08-01T09:00:00Z",
                        None,
                        None,
                        status,
                    ]
                ]
            )

        if "MATCH (source {id:$source_id})-[r]-(target {id:$target_id})" in cypher:
            if not self.evidence:
                return Result(
                    [
                        [
                            "commit-001",
                            "CHANGED",
                            "dependency-001",
                            "edge-001",
                            "2026-08-01T09:00:00Z",
                            None,
                            None,
                            EvidenceStatus.UNKNOWN,
                            [],
                            [],
                            [],
                            [],
                            [],
                            [],
                        ]
                    ]
                )
            source_status = (
                EvidenceStatus.CONTRADICTED
                if self.contradiction
                else EvidenceStatus.OBSERVED
            )
            return Result(
                [
                    [
                        "commit-001",
                        "CHANGED",
                        "dependency-001",
                        "edge-001",
                        "2026-08-01T09:00:00Z",
                        None,
                        None,
                        EvidenceStatus.OBSERVED,
                        ["source-001"],
                        [source_status],
                        ["2026-08-01T09:05:00Z"],
                        ["record-001"],
                        ["span-1"],
                        ["source one"],
                    ]
                ]
            )

        if "MATCH (subject {id:$subject}), (object {id:$object})" in cypher:
            if self.temporal == "invalid":
                return Result(
                    [
                        [
                            "commit-001",
                            {"id": "commit-001", "timestamp": "2026-08-01T10:30:00Z"},
                            "dependency-001",
                            {"id": "dependency-001"},
                        ]
                    ]
                )
            return Result(
                [
                    [
                        "commit-001",
                        {"id": "commit-001", "timestamp": "2026-08-01T09:00:00Z"},
                        "dependency-001",
                        {"id": "dependency-001"},
                    ]
                ]
            )

        return Result([])


def _claim() -> Claim:
    return Claim("commit-001", "CHANGED", "dependency-001")


def test_supported_relationship_is_observed_and_runs_full_pipeline():
    graph = FakeGraph()
    result = EvidenceValidator(graph).validate(_claim())

    assert result.classification == ClaimClassification.OBSERVED
    assert result.supported
    assert result.graph_valid
    assert result.evidence_found
    assert result.temporal_check is not None
    assert result.temporal_check.valid is True
    assert result.contradictions == ()
    assert result.pipeline == (
        "graph_validation",
        "evidence_lookup",
        "temporal_check",
        "contradiction_check",
        "evidence_classification",
    )


def test_graph_validation_requires_exact_directed_relationship():
    graph = FakeGraph(exists=False)
    result = EvidenceValidator(graph).validate(
        Claim("dependency-001", "CHANGED", "commit-001")
    )

    assert result.classification == ClaimClassification.UNKNOWN
    query = graph.calls[0][0]
    assert "->(target" in query


def test_absent_relationship_is_unknown_not_true():
    result = EvidenceValidator(FakeGraph(exists=False)).validate(_claim())

    assert result.classification == ClaimClassification.UNKNOWN
    assert not result.supported
    assert not result.graph_valid
    assert result.pipeline == (
        "graph_validation",
        "evidence_lookup",
        "temporal_check",
        "contradiction_check",
        "evidence_classification",
    )
    assert result.message == "Insufficient evidence."


def test_temporal_impossibility_contradicts_existing_relationship():
    result = EvidenceValidator(FakeGraph(temporal="invalid")).validate(_claim())

    assert result.classification == ClaimClassification.CONTRADICTED
    assert result.temporal_check is not None
    assert result.temporal_check.valid is False
    assert result.contradictions
    assert "rejected" in result.contradictions[0]


def test_conflicting_source_evidence_is_contradicted():
    result = EvidenceValidator(FakeGraph(contradiction=True)).validate(_claim())

    assert result.classification == ClaimClassification.CONTRADICTED
    assert result.evidence[0].status == EvidenceStatus.CONTRADICTED
    assert any("source-001" in item for item in result.contradictions)


def test_existing_relationship_without_supporting_evidence_is_unknown():
    result = EvidenceValidator(FakeGraph(evidence=False)).validate(_claim())

    assert result.classification == ClaimClassification.UNKNOWN
    assert result.graph_valid
    assert not result.evidence_found
    assert result.message == "Insufficient evidence."


def test_investigator_exposes_m9_as_a_deterministic_boundary():
    from continuum.investigator import Investigator

    result = Investigator(FakeGraph()).validate_claim(_claim())
    assert result.classification == ClaimClassification.OBSERVED


def test_investigator_validation_composes_m6_conflict_primitive(monkeypatch):
    from continuum.investigator import Investigator

    investigator = Investigator(FakeGraph())
    calls = []

    def conflict_checker(paths):
        calls.append(paths)
        return ["M6 conflict primitive invoked"]

    monkeypatch.setattr(investigator, "find_conflicting_evidence", conflict_checker)
    result = investigator.validate_claim(_claim())

    assert calls
    assert result.classification == ClaimClassification.CONTRADICTED
    assert result.contradictions == ("M6 conflict primitive invoked",)
