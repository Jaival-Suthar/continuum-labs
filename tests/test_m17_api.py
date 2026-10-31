from __future__ import annotations

from continuum.api.service import InvestigationService
from continuum.core import Evidence, EvidenceStatus, InvestigationPath


def test_path_projection_preserves_actual_path_contract():
    path = InvestigationPath(
        node_ids=("a", "b"),
        relationships=("CAUSES",),
        edge_ids=("edge-1",),
        temporal_status="VALID",
        temporal_reason="ordered",
        evidence=(Evidence("e1", "source-1", EvidenceStatus.OBSERVED),),
        supporting_relationship_count=1,
    )
    payload = InvestigationService._path_dict(path)
    assert payload["id"]
    assert payload["node_ids"] == ["a", "b"]
    assert payload["relationships"] == ["CAUSES"]
    assert payload["edge_ids"] == ["edge-1"]
    assert payload["temporally_valid"] is True
    assert payload["evidence_ids"] == ["e1"]


def test_path_projection_retains_unknown_temporal_state():
    path = InvestigationPath(
        node_ids=("a", "b"),
        relationships=("CAUSES",),
        edge_ids=("edge-1",),
        temporal_status="UNKNOWN",
        temporal_reason="insufficient timestamps",
    )
    assert InvestigationService._path_dict(path)["temporally_valid"] is None


def test_status_does_not_turn_insufficient_evidence_into_application_failure():
    class Result:
        target = "incident-001"

    assert (
        InvestigationService._status(Result(), {"outcome": "INSUFFICIENT"})
        == "INSUFFICIENT_EVIDENCE"
    )


def test_status_preserves_ambiguous_competition():
    class Result:
        target = "impact-001"

    assert (
        InvestigationService._status(Result(), {"outcome": "AMBIGUOUS"}) == "AMBIGUOUS"
    )
