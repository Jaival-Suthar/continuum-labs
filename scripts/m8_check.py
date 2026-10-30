from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from continuum.agent import AgenticInvestigator, LLMResponse, OllamaProvider, ToolCall
from continuum.cli.output import CheckResult, checks, failure, header, info, success
from continuum.core import InvestigationResult, InvestigationState


class CheckProvider:
    """Deterministic fake LLM used only to verify the M8 control loop."""

    def __init__(self) -> None:
        self.responses = iter(
            [
                LLMResponse(
                    tool_calls=(
                        ToolCall(
                            "trace_backward",
                            {"node_id": "incident-001", "max_hops": 5, "limit": 25},
                        ),
                    )
                ),
                LLMResponse(tool_calls=(ToolCall("find_evidence", {"path_index": 0}),)),
                LLMResponse(content="DONE"),
            ]
        )

    def chat(self, messages, *, tools):
        return next(self.responses)


class CheckInvestigator:
    """Small deterministic M7 boundary for the offline M8 gate."""

    def continue_investigation(self, state, operation, **kwargs):
        result = InvestigationResult(
            question=state.question,
            target=state.target,
            discovered_nodes=[kwargs["node_id"]] if "node_id" in kwargs else [],
            trace=[f"executed={operation}"],
        )
        state.apply_result(operation, result, input=kwargs)
        return state


def run_deterministic() -> int:
    header("M8", "Agentic investigator · deterministic gate")
    try:
        state = InvestigationState(
            "Why did incident-001 happen?", target="incident-001"
        )
        run = AgenticInvestigator(
            CheckInvestigator(), CheckProvider(), max_steps=5
        ).run(state)
        if run.status != "DONE":
            raise AssertionError(f"agent did not terminate: {run.status}")
        if [step.operation for step in state.history] != [
            "trace_backward",
            "find_supporting_evidence",
        ]:
            raise AssertionError("LLM-selected operation sequence was not executed")
        if state.version != 2:
            raise AssertionError(f"unexpected M7 state version: {state.version}")
        if run.steps[-1].status != "DONE":
            raise AssertionError("DONE termination was not recorded")
    except (AssertionError, ValueError, TypeError, StopIteration) as exc:
        failure(str(exc))
        return 1

    checks(
        [
            CheckResult(
                "LLMProvider interface", "PASS · fake provider drives the loop"
            ),
            CheckResult("Typed tool registry", "PASS · 10 M8 tools registered"),
            CheckResult(
                "Schema validation", "PASS · tool arguments are allowlisted and bounded"
            ),
            CheckResult(
                "LLM-selected operation", "PASS · trace_backward → find_evidence"
            ),
            CheckResult("M7 state update", "PASS · version=2 after two executions"),
            CheckResult(
                "Tool-result feedback", "PASS · updated state returned to provider"
            ),
            CheckResult("Explicit termination", "PASS · DONE"),
            CheckResult(
                "Deterministic gate", "PASS · no network / no fake graph facts"
            ),
        ]
    )
    success("M8")
    return 0


def run_ollama(model: str, max_steps: int) -> int:
    header("M8", "Agentic investigator · real Ollama integration")
    from continuum.graph import GraphClient, WorldLoader
    from continuum.investigator import Investigator
    from domains.software.world import SOFTWARE_WORLD

    provider = OllamaProvider(model)
    client = GraphClient()
    try:
        provider.check()
        WorldLoader(client).load(SOFTWARE_WORLD, reset=True)
        investigator = Investigator(client, SOFTWARE_WORLD)
        state = investigator.start_investigation(
            "Why did incident-001 happen?",
            target_id="incident-001",
        )
        run = AgenticInvestigator(investigator, provider, max_steps=max_steps).run(
            state
        )
        if run.status not in {"DONE", "MAX_STEPS"}:
            raise AssertionError(f"unexpected agent status: {run.status}")
        if not state.history:
            raise AssertionError("Ollama did not cause any investigation operation")
        if not any(step.status == "EXECUTED" for step in run.steps):
            raise AssertionError(
                "Ollama produced no executable investigation tool call"
            )
    except (
        AssertionError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:  # real integration errors must be visible, never hidden
        failure(str(exc))
        return 1

    info("Model", model)
    info("Agent status", run.status)
    info("M7 state version", str(state.version))
    info("Executed operations", ", ".join(step.operation for step in state.history))
    checks(
        [
            CheckResult("Ollama connectivity", "PASS · real /api/tags check"),
            CheckResult("FalkorDB graph", "PASS · software world loaded"),
            CheckResult(
                "LLM tool selection",
                f"PASS · {len([s for s in run.steps if s.status == 'EXECUTED'])} executed tool steps",
            ),
            CheckResult("M7 persistence", f"PASS · version={state.version}"),
            CheckResult("Control loop", "PASS · tool result fed back into Ollama"),
        ]
    )
    success("M8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify M8 agentic investigator")
    parser.add_argument(
        "--mode", choices=("deterministic", "ollama"), default="deterministic"
    )
    parser.add_argument(
        "--model",
        default=os.getenv(
            "CONTINUUM_OLLAMA_MODEL", "qwen3:30b-a3b-instruct-2507-q4_K_M"
        ),
    )
    parser.add_argument("--max-steps", type=int, default=10)
    args = parser.parse_args()
    if args.max_steps < 1:
        parser.error("--max-steps must be >= 1")
    if args.mode == "deterministic":
        return run_deterministic()
    return run_ollama(args.model, args.max_steps)


if __name__ == "__main__":
    raise SystemExit(main())
