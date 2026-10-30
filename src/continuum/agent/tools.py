from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from continuum.core import InvestigationResult, InvestigationState


class ToolExecutionError(RuntimeError):
    """A validated tool call could not be executed."""


class InvestigationTool(Protocol):
    name: str
    description: str

    def schema(self) -> dict[str, Any]: ...

    def execute(
        self,
        investigator: Any,
        state: InvestigationState,
        arguments: dict[str, Any],
    ) -> InvestigationState: ...


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    properties: dict[str, dict[str, Any]]
    required: tuple[str, ...] = ()
    additional_properties: bool = False

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.properties,
                    "required": list(self.required),
                    "additionalProperties": self.additional_properties,
                },
            },
        }

    def validate(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ToolExecutionError(f"arguments for {self.name} must be an object")
        unknown = sorted(set(arguments) - set(self.properties))
        if unknown and not self.additional_properties:
            raise ToolExecutionError(
                f"invalid arguments for {self.name}: unknown fields={unknown}"
            )
        missing = [name for name in self.required if name not in arguments]
        if missing:
            raise ToolExecutionError(
                f"invalid arguments for {self.name}: missing required fields={missing}"
            )
        for name, value in arguments.items():
            if name not in self.properties:
                continue
            expected = self.properties[name].get("type")
            if expected == "string" and not isinstance(value, str):
                raise ToolExecutionError(f"{name} must be a string")
            if expected == "integer" and (
                not isinstance(value, int) or isinstance(value, bool)
            ):
                raise ToolExecutionError(f"{name} must be an integer")
            if expected == "array" and not isinstance(value, list):
                raise ToolExecutionError(f"{name} must be an array")
            if expected == "object" and not isinstance(value, dict):
                raise ToolExecutionError(f"{name} must be an object")

            minimum = self.properties[name].get("minimum")
            if minimum is not None and isinstance(value, int) and value < minimum:
                raise ToolExecutionError(f"{name} must be >= {minimum}")
            maximum = self.properties[name].get("maximum")
            if maximum is not None and isinstance(value, int) and value > maximum:
                raise ToolExecutionError(f"{name} must be <= {maximum}")
            min_length = self.properties[name].get("minLength")
            if (
                min_length is not None
                and isinstance(value, str)
                and len(value) < min_length
            ):
                raise ToolExecutionError(f"{name} must not be empty")
        return dict(arguments)


class M8Tool:
    spec: ToolSpec

    def execute(
        self,
        investigator: Any,
        state: InvestigationState,
        arguments: dict[str, Any],
    ) -> InvestigationState:
        validated = self.spec.validate(arguments)
        try:
            return investigator.continue_investigation(
                state, self.runtime_operation, **validated
            )
        except (AssertionError, IndexError, KeyError, TypeError, ValueError) as exc:
            raise ToolExecutionError(
                f"{self.spec.name} execution failed: {exc}"
            ) from exc


class SearchEntitiesTool(M8Tool):
    runtime_operation = "find_outcome"
    spec = ToolSpec(
        "search_entities",
        "Locate a graph entity relevant to a natural-language investigation query. The graph decides which entity exists.",
        {"query": {"type": "string", "minLength": 1}},
        ("query",),
    )

    def execute(
        self,
        investigator: Any,
        state: InvestigationState,
        arguments: dict[str, Any],
    ) -> InvestigationState:
        validated = self.spec.validate(arguments)
        try:
            return investigator.continue_investigation(
                state, "find_outcome", target_or_question=validated["query"]
            )
        except (AssertionError, IndexError, KeyError, TypeError, ValueError) as exc:
            raise ToolExecutionError(
                f"{self.spec.name} execution failed: {exc}"
            ) from exc


class QueryGraphTool(M8Tool):
    runtime_operation = "find_paths"
    spec = ToolSpec(
        "query_graph",
        "Find actual graph paths between two existing node IDs. This is a structured investigation operation, not arbitrary Cypher.",
        {
            "start_id": {"type": "string", "minLength": 1},
            "end_id": {"type": "string", "minLength": 1},
            "max_hops": {"type": "integer", "minimum": 1, "maximum": 12},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        ("start_id", "end_id"),
    )


class ExpandNodeTool(M8Tool):
    runtime_operation = "expand_neighborhood"
    spec = ToolSpec(
        "expand_node",
        "Expand the connected neighborhood of a known node.",
        {
            "node_id": {"type": "string", "minLength": 1},
            "depth": {"type": "integer", "minimum": 1, "maximum": 6},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
    )


class TraceBackwardTool(M8Tool):
    runtime_operation = "trace_backward"
    spec = ToolSpec(
        "trace_backward",
        "Trace graph relationships backward from a known target to discover preceding candidate paths.",
        {
            "node_id": {"type": "string", "minLength": 1},
            "max_hops": {"type": "integer", "minimum": 1, "maximum": 12},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
    )


class TraceForwardTool(M8Tool):
    runtime_operation = "trace_forward"
    spec = ToolSpec(
        "trace_forward",
        "Trace downstream graph paths from a known node.",
        {
            "node_id": {"type": "string", "minLength": 1},
            "max_hops": {"type": "integer", "minimum": 1, "maximum": 12},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
    )


class FindPathsTool(M8Tool):
    runtime_operation = "find_paths"
    spec = ToolSpec(
        "find_paths",
        "Find candidate graph paths between two known node IDs.",
        {
            "start_id": {"type": "string", "minLength": 1},
            "end_id": {"type": "string", "minLength": 1},
            "max_hops": {"type": "integer", "minimum": 1, "maximum": 12},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        ("start_id", "end_id"),
    )


class FindChangesTool(M8Tool):
    runtime_operation = "find_preceding_changes"
    spec = ToolSpec(
        "find_changes",
        "Find timestamped candidate changes preceding the current investigation target.",
        {
            "outcome_id": {"type": "string", "minLength": 1},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
    )


class FindEvidenceTool(M8Tool):
    runtime_operation = "find_supporting_evidence"
    spec = ToolSpec(
        "find_evidence",
        "Resolve provenance evidence attached to one candidate investigation path.",
        {"path_index": {"type": "integer", "minimum": 0}},
        ("path_index",),
    )


class CheckTemporalConsistencyTool(M8Tool):
    runtime_operation = "check_temporal_consistency"
    spec = ToolSpec(
        "check_temporal_consistency",
        "Check whether the events on one candidate path are temporally consistent.",
        {"path_index": {"type": "integer", "minimum": 0}},
        ("path_index",),
    )


class CompareHypothesesTool(M8Tool):
    """Expose M7 hypothesis state without performing M10 competition."""

    spec = ToolSpec(
        "compare_hypotheses",
        "Inspect the currently stored hypotheses side-by-side. This operation does not rank, score, validate, or select a winning hypothesis.",
        {},
    )

    def execute(
        self,
        investigator: Any,
        state: InvestigationState,
        arguments: dict[str, Any],
    ) -> InvestigationState:
        self.spec.validate(arguments)
        result = InvestigationResult(
            question=state.question,
            target=state.target,
            trace=[f"hypotheses_inspected={len(state.hypotheses)}"],
        )
        state.apply_result("compare_hypotheses", result, input={})
        return state


M8_TOOLS: tuple[InvestigationTool, ...] = (
    SearchEntitiesTool(),
    QueryGraphTool(),
    ExpandNodeTool(),
    TraceBackwardTool(),
    TraceForwardTool(),
    FindPathsTool(),
    FindChangesTool(),
    FindEvidenceTool(),
    CheckTemporalConsistencyTool(),
    CompareHypothesesTool(),
)
