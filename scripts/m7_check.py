from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from continuum.cli.output import CheckResult, checks, failure, header, success
from continuum.core import Hypothesis, InvestigationState
from continuum.graph import GraphClient, WorldLoader
from continuum.investigator import Investigator
from domains.software.world import SOFTWARE_WORLD


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    header("M7", "Persistent investigation state")
    client = GraphClient()

    try:
        WorldLoader(client).load(SOFTWARE_WORLD, reset=True)
        investigator = Investigator(client, SOFTWARE_WORLD)

        state = investigator.start_investigation(
            "Why did incident-001 happen?",
            hypotheses=(
                Hypothesis("H1", "Dependency change"),
                Hypothesis("H2", "Configuration change"),
                Hypothesis("H3", "Infrastructure event"),
            ),
        )

        if not isinstance(state, InvestigationState):
            fail("start_investigation did not return InvestigationState")
        if state.version != 0:
            fail(f"initial state version must be 0, got {state.version}")
        if state.target is not None:
            fail("initial state unexpectedly has a target")
        if state.candidate_paths or state.evidence:
            fail("initial state unexpectedly contains investigation results")

        investigator.continue_investigation(state, "find_outcome")
        if state.target != "incident-001":
            fail(f"outcome was not persisted: {state.target}")
        if state.version != 1:
            fail("find_outcome did not create state version 1")

        # No node_id is supplied: this step must consume state from step 1.
        investigator.continue_investigation(state, "expand_neighborhood", depth=2)
        if "incident-001" not in state.explored_nodes:
            fail("step 2 did not retain the target from step 1")
        if "deployment-001" not in state.explored_nodes:
            fail("step 2 did not explore the expected neighborhood")
        if state.version != 2:
            fail("expand_neighborhood did not create state version 2")

        # No node_id is supplied: this step must consume the same target/state.
        investigator.continue_investigation(
            state,
            "trace_backward",
            max_hops=5,
            limit=25,
        )
        if not state.candidate_paths:
            fail("trace_backward did not persist candidate paths")
        if not state.explored_nodes or not state.explored_edges:
            fail("path traversal did not accumulate explored nodes and edges")
        if state.version != 3:
            fail("trace_backward did not create state version 3")

        primary = next(
            (
                path
                for path in state.candidate_paths
                if path.node_ids
                == (
                    "commit-001",
                    "dependency-gateway-sdk",
                    "service-payments",
                    "deployment-001",
                    "metric-001",
                    "incident-001",
                )
            ),
            None,
        )
        if primary is None:
            fail("primary multi-hop path was not retained in investigation state")

        investigator.continue_investigation(
            state,
            "find_supporting_evidence",
            path=primary,
        )
        if not state.evidence:
            fail("supporting evidence was not accumulated")
        if state.version != 4:
            fail("find_supporting_evidence did not create state version 4")

        investigator.continue_investigation(
            state,
            "check_temporal_consistency",
            path=primary,
        )
        if not any("VALID" in constraint for constraint in state.temporal_constraints):
            fail("temporal constraint was not persisted")
        if state.version != 5:
            fail("check_temporal_consistency did not create state version 5")

        investigator.continue_investigation(
            state,
            "find_conflicting_evidence",
        )
        if not state.contradictions:
            fail("contradictions were not accumulated")
        if not state.gaps:
            fail("evidence gaps were not accumulated")
        if state.version != 6:
            fail("find_conflicting_evidence did not create state version 6")

        investigator.continue_investigation(state, "rank_paths")
        if state.version != 7:
            fail("rank_paths did not create state version 7")

        hypothesis_ids = [hypothesis.id for hypothesis in state.hypotheses]
        if hypothesis_ids != ["H1", "H2", "H3"]:
            fail(f"hypotheses were not persisted: {hypothesis_ids}")

        expected_history = [
            "find_outcome",
            "expand_neighborhood",
            "trace_backward",
            "find_supporting_evidence",
            "check_temporal_consistency",
            "find_conflicting_evidence",
            "rank_paths",
        ]
        if [step.operation for step in state.history] != expected_history:
            fail("investigation history does not preserve the operation sequence")
        if state.history[0].result.target != "incident-001":
            fail("history lost the result from the first investigation step")
        if state.history[1].input != {"depth": 2}:
            fail("step 2 did not record its explicit operation input")
        if state.history[2].input != {"max_hops": 5, "limit": 25}:
            fail("step 3 did not record its explicit operation input")

        nodes_before = set(state.explored_nodes)
        edges_before = set(state.explored_edges)
        paths_before = len(state.candidate_paths)
        evidence_before = len(state.evidence)

        # Repeat a prior operation. History grows, but cumulative collections do not.
        investigator.continue_investigation(
            state,
            "trace_backward",
            max_hops=5,
            limit=25,
        )
        if state.explored_nodes != nodes_before:
            fail("repeated exploration duplicated or changed explored nodes")
        if state.explored_edges != edges_before:
            fail("repeated exploration duplicated or changed explored edges")
        if len(state.candidate_paths) != paths_before:
            fail("repeated exploration duplicated candidate paths")
        if len(state.evidence) != evidence_before:
            fail("repeated exploration duplicated evidence")
        if state.history[-1].state_version != 8:
            fail("repeated operation did not advance history version")
        if state.history[-1].added_path_count != 0:
            fail("repeated operation was not idempotent")

    except (AssertionError, ValueError, TypeError, IndexError) as exc:
        failure(str(exc))
        return 1

    checks(
        [
            CheckResult("Initial state", "PASS · version=0 · empty investigation"),
            CheckResult("Outcome persisted", "PASS · target=incident-001"),
            CheckResult(
                "Explored nodes accumulated",
                f"PASS · {len(state.explored_nodes)} unique nodes",
            ),
            CheckResult(
                "Explored edges accumulated",
                f"PASS · {len(state.explored_edges)} unique edges",
            ),
            CheckResult(
                "Candidate paths persisted",
                f"PASS · {len(state.candidate_paths)} unique paths",
            ),
            CheckResult(
                "Evidence accumulated",
                f"PASS · {len(state.evidence)} unique records",
            ),
            CheckResult(
                "Contradictions accumulated",
                f"PASS · {len(state.contradictions)} unique contradictions",
            ),
            CheckResult(
                "Evidence gaps accumulated",
                f"PASS · {len(state.gaps)} unique gaps",
            ),
            CheckResult(
                "Temporal constraints persisted",
                f"PASS · {len(state.temporal_constraints)} constraints",
            ),
            CheckResult(
                "Hypotheses persisted",
                f"PASS · {len(state.hypotheses)} hypotheses",
            ),
            CheckResult(
                "Investigation history persisted",
                f"PASS · {len(state.history)} recorded steps",
            ),
            CheckResult(
                "Cumulative state updates",
                "PASS · repeated exploration adds no duplicate state",
            ),
            CheckResult(
                "Multi-step continuation",
                "PASS · later operations consumed the same state",
            ),
        ]
    )
    success("M7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
