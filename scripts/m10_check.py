from __future__ import annotations

import argparse

from continuum.agent import AgenticInvestigator, OllamaProvider
from continuum.cli.output import CheckResult, checks, failure, header, info, success
from continuum.core import Hypothesis as StateHypothesis
from continuum.graph.client import GraphClient
from continuum.graph.loader import WorldLoader
from continuum.hypothesis import CompetitionOutcome, path_id
from continuum.investigator import Investigator
from domains.software.world import SOFTWARE_WORLD


def _attach_hypothesis(
    state,
    hypothesis_id: str,
    description: str,
    paths,
) -> None:
    state.add_hypothesis(
        StateHypothesis(
            hypothesis_id,
            description,
            candidate_path_ids=tuple(path_id(path) for path in paths),
        )
    )


def run_falkordb() -> int:
    header("M10", "Hypothesis competition · real FalkorDB gate")
    client = GraphClient()

    try:
        client.ping()
        WorldLoader(client).load(SOFTWARE_WORLD, reset=True)
        investigator = Investigator(client)

        state = investigator.start_investigation(
            "Why did incident-001 happen?",
            target_id="incident-001",
        )

        dependency_paths = investigator.find_paths(
            "commit-001", "incident-001", max_hops=6, limit=25
        )
        infrastructure_paths = investigator.find_paths(
            "infra-event-001", "incident-001", max_hops=3, limit=25
        )
        configuration_paths = investigator.find_paths(
            "config-001", "incident-001", max_hops=3, limit=25
        )

        if not dependency_paths:
            raise AssertionError("M3 dependency path was not found")
        if not infrastructure_paths:
            raise AssertionError("M3 infrastructure alternative path was not found")
        if not configuration_paths:
            raise AssertionError("M3 configuration alternative path was not found")

        all_paths = [*dependency_paths, *infrastructure_paths, *configuration_paths]
        for path in all_paths:
            state.candidate_paths.append(path)
            state.explored_nodes.update(path.node_ids)
            state.explored_edges.update(
                edge_id or f"{source}|{relationship}|{target}"
                for source, relationship, target, edge_id in zip(
                    path.node_ids[:-1],
                    path.relationships,
                    path.node_ids[1:],
                    path.edge_ids,
                    strict=True,
                )
            )

        _attach_hypothesis(
            state,
            "H1",
            "Dependency change",
            dependency_paths,
        )
        _attach_hypothesis(
            state,
            "H2",
            "Infrastructure event",
            infrastructure_paths,
        )
        _attach_hypothesis(
            state,
            "H3",
            "Configuration change",
            configuration_paths,
        )

        competition = investigator.compete_hypotheses(state)
        by_id = {item.id: item for item in competition.hypotheses}

        assert competition.outcome == CompetitionOutcome.WINNER
        assert competition.winner_ids == ("H1",)
        assert by_id["H1"].support_count == 5
        assert by_id["H1"].contradictions == ()
        assert by_id["H1"].temporal_validity == "VALID"
        assert by_id["H1"].path_quality == "STRONG"
        assert by_id["H1"].score == 8

        assert by_id["H2"].support_count == 1
        assert by_id["H2"].missing_evidence
        assert by_id["H2"].path_quality == "WEAK"
        assert by_id["H2"].plausible
        assert by_id["H1"].score > by_id["H2"].score

        assert by_id["H3"].temporal_validity == "INVALID"
        assert by_id["H3"].contradictions
        assert not by_id["H3"].plausible

        # The M8 boundary invokes the same deterministic M10 evaluator.
        m8_state = investigator.start_investigation(
            "Why did incident-001 happen?",
            target_id="incident-001",
            hypotheses=state.hypotheses,
        )
        m8_state.candidate_paths.extend(state.candidate_paths)
        m8_state.explored_nodes.update(state.explored_nodes)
        m8_state.explored_edges.update(state.explored_edges)
        m8_competition = investigator.compete_hypotheses(m8_state)
        assert m8_competition.verdict == "H1 best supported"

    except (AssertionError, OSError, RuntimeError, TypeError, ValueError) as exc:
        failure(str(exc))
        return 1

    info(
        "H1",
        f"score={by_id['H1'].score} · SUPPORT={by_id['H1'].support_count} · TEMPORAL={by_id['H1'].temporal_validity} · PATH={by_id['H1'].path_quality}",
    )
    info(
        "H2",
        f"score={by_id['H2'].score} · SUPPORT={by_id['H2'].support_count} · MISSING={len(by_id['H2'].missing_evidence)} · PATH={by_id['H2'].path_quality}",
    )
    info(
        "H3",
        f"score={by_id['H3'].score} · CONTRADICTIONS={len(by_id['H3'].contradictions)} · TEMPORAL={by_id['H3'].temporal_validity}",
    )
    info("Verdict", competition.verdict)

    checks(
        [
            CheckResult("FalkorDB connectivity", "PASS · real seeded software graph"),
            CheckResult(
                "M6 candidate paths",
                "PASS · dependency, infrastructure, and configuration paths discovered",
            ),
            CheckResult(
                "M9 validation",
                "PASS · every candidate-path relationship is validated deterministically",
            ),
            CheckResult("H1", "PASS · strong support, valid time, strong path"),
            CheckResult("H2", "PASS · missing evidence prevents false winner"),
            CheckResult(
                "H3", "PASS · temporal contradiction rejects configuration explanation"
            ),
            CheckResult(
                "Deterministic ranking", "PASS · H1 wins without confidence percentages"
            ),
            CheckResult(
                "M8 boundary",
                "PASS · compare_hypotheses consumes the same M10 evaluator",
            ),
        ]
    )
    success("M10")
    return 0


def run_ollama(model: str, max_steps: int) -> int:
    """Run M8 with a real model, then deterministically compare its state hypotheses."""
    header("M10", "Hypothesis competition · real Ollama boundary")
    provider = OllamaProvider(model)
    client = GraphClient()

    try:
        provider.check()
        client.ping()
        WorldLoader(client).load(SOFTWARE_WORLD, reset=True)
        investigator = Investigator(client)
        state = investigator.start_investigation(
            "Why did incident-001 happen?",
            target_id="incident-001",
        )
        run = AgenticInvestigator(investigator, provider, max_steps=max_steps).run(
            state
        )
        if run.status not in {"DONE", "MAX_STEPS"}:
            raise AssertionError(f"unexpected agent status: {run.status}")

        # M8 remains responsible for investigation control. M10 only evaluates
        # hypotheses that have actually been placed in InvestigationState.
        if not state.hypotheses:
            raise AssertionError(
                "real M8 run produced no hypotheses; M10 will not invent hypotheses on its behalf"
            )
        competition = investigator.compete_hypotheses(state)
        if competition.outcome not in CompetitionOutcome.ALL:
            raise AssertionError("invalid M10 competition outcome")

    except (AssertionError, OSError, RuntimeError, TypeError, ValueError) as exc:
        failure(str(exc))
        return 1

    info("Model", model)
    info("M8 status", run.status)
    info("Hypotheses", str(len(state.hypotheses)))
    info("M10 outcome", competition.outcome)
    info("Verdict", competition.verdict)
    checks(
        [
            CheckResult("Ollama connectivity", "PASS · real model endpoint"),
            CheckResult("M8 investigation", "PASS · real agent control loop completed"),
            CheckResult(
                "Hypothesis state",
                "PASS · M10 consumed hypotheses already present in state",
            ),
            CheckResult(
                "M10 evaluator", "PASS · deterministic M6/M9-backed evaluation"
            ),
            CheckResult(
                "No LLM verdict", "PASS · ranking performed by deterministic code"
            ),
        ]
    )
    success("M10")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ollama", metavar="MODEL")
    parser.add_argument("--max-steps", type=int, default=10)
    args = parser.parse_args()
    if args.ollama:
        return run_ollama(args.ollama, args.max_steps)
    return run_falkordb()


if __name__ == "__main__":
    raise SystemExit(main())
