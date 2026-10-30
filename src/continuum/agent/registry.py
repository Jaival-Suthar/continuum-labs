from __future__ import annotations

from typing import Any

from continuum.agent.tools import M8_TOOLS, InvestigationTool, ToolExecutionError


class ToolRegistry:
    """Allowlisted M8 tool registry and validation boundary."""

    def __init__(self, tools: tuple[InvestigationTool, ...] = M8_TOOLS):
        self._tools = {
            tool.name if hasattr(tool, "name") else tool.spec.name: tool
            for tool in tools
        }

    def get(self, name: str) -> InvestigationTool:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolExecutionError(
                f"unknown investigation tool: {name}; allowed={', '.join(self.names())}"
            )
        return tool

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def schemas(self) -> list[dict[str, Any]]:
        return [self._tools[name].spec.schema() for name in sorted(self._tools)]
