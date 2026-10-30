from __future__ import annotations

from datetime import UTC, datetime

from continuum.core import (
    Evidence,
    EvidenceStatus,
    Hypothesis,
    InvestigationPath,
    InvestigationResult,
    InvestigationState,
)
from continuum.investigator import Investigator


def _path() -> InvestigationPath:
    timestamp = datetime(2026, 8, 1, 9, tzinfo=UTC)
    return InvestigationPath(
        node_ids=("commit-001", "incident-001"),
        relationships=("RESULTED_IN",),
        edge_ids=("edge-001",),
        temporal_status="VALID",
        temporal_reason="path temporally consistent",
        evidence=(
            Evidence(
                "source-001",
                "source-001",
                EvidenceStatus.OBSERVED,
                observed_at=timestamp,
            ),
        ),
        supporting_relationship_count=1,
    )


def test_investigation_state_merges_results_idempotently():
    path = _path()
    evidence = path.evidence[0]
    state = InvestigationState(
        question="Why did incident-001 happen?",
        target="incident-001",
        hypotheses=[
            Hypothesis("H1", "Dependency change"),
            Hypothesis("H2", "Configuration change"),
            Hypothesis("H3", "Infrastructure event"),
        ],
    )
    result = InvestigationResult(
        question=state.question,
        target="incident-001",
        discovered_nodes=["incident-001", "commit-001"],
        discovered_edges=["edge-001"],
        candidate_paths=[path],
        evidence=[evidence],
        contradictions=["configuration path rejected"],
        gaps=["infrastructure evidence missing"],
        temporal_checks=["commit-001 -> incident-001: VALID"],
    )

    first = state.apply_result("trace_backward", result)
    second = state.apply_result("trace_backward", result)

    assert first.state_version == 1
    assert second.state_version == 2
    assert state.target == "incident-001"
    assert state.explored_nodes == {"commit-001", "incident-001"}
    assert state.explored_edges == {"edge-001"}
    assert state.candidate_paths == [path]
    assert state.evidence == [evidence]
    assert state.contradictions == ["configuration path rejected"]
    assert state.gaps == ["infrastructure evidence missing"]
    assert state.temporal_constraints == ["commit-001 -> incident-001: VALID"]
    assert [hypothesis.id for hypothesis in state.hypotheses] == ["H1", "H2", "H3"]
    assert len(state.history) == 2
    assert first.added_path_count == 1
    assert second.added_path_count == 0
    assert second.added_evidence_count == 0
    assert second.added_nodes == ()
    assert second.added_edges == ()


def test_investigation_state_hypothesis_updates_are_merged_by_id():
    state = InvestigationState("Why did incident-001 happen?")
    state.add_hypothesis(Hypothesis("H1", "Dependency change", evidence_ids=("e1",)))
    state.add_hypothesis(
        Hypothesis(
            "H1",
            "Dependency change",
            candidate_path_ids=("p1",),
            evidence_ids=("e1", "e2"),
            gaps=("g1",),
        )
    )

    assert len(state.hypotheses) == 1
    assert state.hypotheses[0].candidate_path_ids == ("p1",)
    assert state.hypotheses[0].evidence_ids == ("e1", "e2")
    assert state.hypotheses[0].gaps == ("g1",)


def test_investigator_continuation_consumes_the_same_state(monkeypatch):
    path = _path()
    investigator = Investigator(object())

    monkeypatch.setattr(
        investigator,
        "find_outcome",
        lambda question, target_id=None: type("Node", (), {"id": "incident-001"})(),
    )
    monkeypatch.setattr(
        investigator,
        "expand_neighborhood",
        lambda node_id, **kwargs: [
            type("Node", (), {"id": "metric-001"})(),
        ],
    )
    monkeypatch.setattr(
        investigator,
        "trace_backward",
        lambda node_id, **kwargs: [path],
    )

    state = investigator.start_investigation(
        "Why did incident-001 happen?",
        hypotheses=(
            Hypothesis("H1", "Dependency change"),
            Hypothesis("H2", "Configuration change"),
            Hypothesis("H3", "Infrastructure event"),
        ),
    )
    assert state.version == 0
    assert state.target is None

    investigator.continue_investigation(state, "find_outcome")
    assert state.version == 1
    assert state.target == "incident-001"
    assert state.candidate_paths == []

    investigator.continue_investigation(state, "expand_neighborhood", depth=2)
    assert state.version == 2
    assert "incident-001" in state.explored_nodes
    assert "metric-001" in state.explored_nodes

    investigator.continue_investigation(state, "trace_backward", max_hops=5, limit=25)
    assert state.version == 3
    assert state.candidate_paths == [path]
    assert state.explored_nodes == {"commit-001", "incident-001", "metric-001"}
    assert state.explored_edges == {"edge-001"}
    assert [step.operation for step in state.history] == [
        "find_outcome",
        "expand_neighborhood",
        "trace_backward",
    ]
    assert state.history[1].input == {"depth": 2}
    assert state.history[2].state_version == 3
