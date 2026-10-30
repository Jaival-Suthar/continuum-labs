from __future__ import annotations

from continuum.agent import (
    AgenticInvestigator,
    LLMResponse,
    ToolCall,
    ToolExecutionError,
    ToolRegistry,
)
from continuum.core import InvestigationResult, InvestigationState


class FakeProvider:
    def __init__(self, responses: list[LLMResponse]):
        self.responses = iter(responses)
        self.calls: list[tuple[list[dict], list[dict]]] = []

    def chat(self, messages, *, tools):
        self.calls.append((list(messages), list(tools)))
        return next(self.responses)


class FakeInvestigator:
    def continue_investigation(self, state, operation, **kwargs):
        result = InvestigationResult(
            question=state.question,
            target=kwargs.get("target_id") or state.target,
            discovered_nodes=[kwargs["node_id"]] if "node_id" in kwargs else [],
            trace=[f"executed={operation}"],
        )
        state.apply_result(operation, result, input=kwargs)
        return state


def test_registry_exposes_exact_m8_tools():
    registry = ToolRegistry()
    assert registry.names() == (
        "check_temporal_consistency",
        "compare_hypotheses",
        "expand_node",
        "find_changes",
        "find_evidence",
        "find_paths",
        "query_graph",
        "search_entities",
        "trace_backward",
        "trace_forward",
    )
    assert len(registry.schemas()) == 10


def test_tool_schema_validation_rejects_unknown_and_out_of_range_arguments():
    registry = ToolRegistry()
    tool = registry.get("trace_backward")
    try:
        tool.spec.validate({"node_id": "incident-001", "max_hops": 99})
    except ToolExecutionError as exc:
        assert "max_hops" in str(exc)
    else:
        raise AssertionError("out-of-range max_hops was accepted")

    try:
        tool.spec.validate({"node_id": "incident-001", "bogus": 1})
    except ToolExecutionError as exc:
        assert "unknown fields" in str(exc)
    else:
        raise AssertionError("unknown argument was accepted")


def test_agent_is_multi_step_state_aware_and_terminates():
    provider = FakeProvider(
        [
            LLMResponse(
                tool_calls=(
                    ToolCall(
                        "trace_backward",
                        {"node_id": "incident-001", "max_hops": 5, "limit": 5},
                    ),
                )
            ),
            LLMResponse(
                tool_calls=(
                    ToolCall("expand_node", {"node_id": "incident-001", "depth": 2}),
                )
            ),
            LLMResponse(content="DONE"),
        ]
    )
    state = InvestigationState("Why did incident-001 happen?", target="incident-001")
    run = AgenticInvestigator(FakeInvestigator(), provider, max_steps=5).run(state)

    assert run.status == "DONE"
    assert run.terminated
    assert state.version == 2
    assert [step.operation for step in state.history] == [
        "trace_backward",
        "expand_neighborhood",
    ]
    assert [step.status for step in run.steps] == ["EXECUTED", "EXECUTED", "DONE"]
    assert provider.calls[0][0][1]["content"].startswith("Investigation question")
    assert "Updated InvestigationState" in provider.calls[1][0][-1]["content"]


def test_agent_recovers_from_invalid_tool_and_continues():
    provider = FakeProvider(
        [
            LLMResponse(tool_calls=(ToolCall("not_a_tool", {}),)),
            LLMResponse(content="DONE"),
        ]
    )
    state = InvestigationState("Why did incident-001 happen?", target="incident-001")
    run = AgenticInvestigator(FakeInvestigator(), provider, max_steps=3).run(state)

    assert run.status == "DONE"
    assert state.version == 0
    assert run.steps[0].status == "RECOVERED"
    assert "unknown investigation tool" in run.steps[0].message


def test_agent_enforces_step_limit():
    provider = FakeProvider(
        [
            LLMResponse(
                tool_calls=(ToolCall("expand_node", {"node_id": "incident-001"}),)
            )
            for _ in range(2)
        ]
    )
    state = InvestigationState("Why did incident-001 happen?", target="incident-001")
    run = AgenticInvestigator(FakeInvestigator(), provider, max_steps=2).run(state)
    assert run.status == "MAX_STEPS"
    assert state.version == 2


def test_ollama_provider_parses_native_tool_calls_without_ollama_package(monkeypatch):
    import json
    from urllib import request

    from continuum.agent import OllamaProvider

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "function": {
                                    "name": "trace_backward",
                                    "arguments": {
                                        "node_id": "incident-001",
                                        "max_hops": 5,
                                    },
                                },
                            }
                        ],
                    }
                }
            ).encode()

    monkeypatch.setattr(request, "urlopen", lambda *args, **kwargs: Response())
    response = OllamaProvider("test-model").chat([], tools=[])
    assert response.tool_calls == (
        ToolCall(
            "trace_backward",
            {"node_id": "incident-001", "max_hops": 5},
            "call-1",
        ),
    )
