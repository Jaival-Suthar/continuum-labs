from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCall:
    """One tool request produced by an LLM provider."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str | None = None


@dataclass(frozen=True)
class LLMResponse:
    """Provider-neutral response consumed by the M8 agent loop."""

    tool_calls: tuple[ToolCall, ...] = ()
    content: str = ""


class LLMProvider(Protocol):
    """Minimal provider contract for the M8 control loop."""

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]],
    ) -> LLMResponse: ...
