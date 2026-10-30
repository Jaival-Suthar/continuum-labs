from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from continuum.agent.llm.base import LLMProvider, ToolCall
from continuum.agent.prompts import SYSTEM_PROMPT, state_context
from continuum.agent.registry import ToolRegistry
from continuum.agent.tools import ToolExecutionError
from continuum.core import InvestigationState


@dataclass(frozen=True)
class AgentStep:
    number: int
    tool_call: ToolCall | None
    status: str
    message: str
    state_version: int


@dataclass
class AgentRun:
    state: InvestigationState
    status: str
    steps: list[AgentStep] = field(default_factory=list)

    @property
    def terminated(self) -> bool:
        return self.status == "DONE"


class AgenticInvestigator:
    """M8 LLM control loop over the deterministic M6/M7 investigator."""

    def __init__(
        self,
        investigator: Any,
        provider: LLMProvider,
        *,
        registry: ToolRegistry | None = None,
        max_steps: int = 10,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        self.investigator = investigator
        self.provider = provider
        self.registry = registry or ToolRegistry()
        self.max_steps = max_steps

    def run(self, state: InvestigationState) -> AgentRun:
        if not isinstance(state, InvestigationState):
            raise TypeError("state must be an InvestigationState")

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": self._context_message(state),
            },
        ]
        steps: list[AgentStep] = []

        for number in range(1, self.max_steps + 1):
            response = self.provider.chat(messages, tools=self.registry.schemas())
            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": response.content,
            }
            if response.tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "function": {
                            "name": call.name,
                            "arguments": call.arguments,
                        },
                        **({"id": call.call_id} if call.call_id else {}),
                    }
                    for call in response.tool_calls
                ]
            messages.append(assistant_message)

            if not response.tool_calls and response.content.strip() == "DONE":
                steps.append(
                    AgentStep(
                        number, None, "DONE", "LLM requested termination", state.version
                    )
                )
                return AgentRun(state, "DONE", steps)

            if not response.tool_calls:
                error_message = (
                    "No tool call was produced. Return exactly DONE when finished, "
                    "otherwise choose one supplied investigation tool."
                )
                messages.append({"role": "user", "content": error_message})
                steps.append(
                    AgentStep(number, None, "RECOVERED", error_message, state.version)
                )
                continue

            if len(response.tool_calls) != 1:
                error_message = (
                    "M8 accepts exactly one tool call per step. Choose one tool."
                )
                messages.append({"role": "user", "content": error_message})
                steps.append(
                    AgentStep(number, None, "RECOVERED", error_message, state.version)
                )
                continue

            call = response.tool_calls[0]
            try:
                tool = self.registry.get(call.name)
                next_state = tool.execute(self.investigator, state, call.arguments)
                if next_state is not state:
                    raise ToolExecutionError(
                        "tool did not update the supplied InvestigationState"
                    )
                result_message = self._latest_result_message(state, call.name)
                messages.append(
                    {
                        "role": "tool",
                        "name": call.name,
                        "content": result_message,
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": f"Updated InvestigationState:\n{state_context(state)}",
                    }
                )
                steps.append(
                    AgentStep(number, call, "EXECUTED", result_message, state.version)
                )
            except ToolExecutionError as exc:
                error_message = f"ToolError: {exc}"
                messages.append(
                    {"role": "tool", "name": call.name, "content": error_message}
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"{error_message}\nCorrect the tool selection or arguments and try again. "
                            f"Current InvestigationState:\n{state_context(state)}"
                        ),
                    }
                )
                steps.append(
                    AgentStep(number, call, "RECOVERED", error_message, state.version)
                )

        return AgentRun(state, "MAX_STEPS", steps)

    @staticmethod
    def _context_message(state: InvestigationState) -> str:
        return (
            "Investigation question and current state:\n"
            f"{state_context(state)}\n\n"
            "Choose the next operation, or respond exactly DONE."
        )

    @staticmethod
    def _latest_result_message(state: InvestigationState, tool_name: str) -> str:
        step = state.history[-1]
        result = step.result
        return str(
            {
                "tool": tool_name,
                "operation": step.operation,
                "state_version": state.version,
                "target": result.target,
                "discovered_nodes": result.discovered_nodes,
                "discovered_edges": result.discovered_edges,
                "candidate_path_count": len(result.candidate_paths),
                "evidence_count": len(result.evidence),
                "contradictions": result.contradictions,
                "gaps": result.gaps,
                "temporal_checks": result.temporal_checks,
                "verdict": result.verdict,
                "hypothesis_competition": state.extensions.get(
                    "hypothesis_competition"
                ),
                "trace": result.trace,
            }
        )
