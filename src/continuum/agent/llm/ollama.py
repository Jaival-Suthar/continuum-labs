from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from continuum.agent.llm.base import LLMResponse, ToolCall


class OllamaError(RuntimeError):
    """Raised when the local Ollama service cannot complete a request."""


class OllamaProvider:
    """LLMProvider backed by Ollama's local HTTP chat API.

    Ollama remains an optional runtime integration: importing Continuum does
    not require the Ollama Python package or a running Ollama server.
    """

    def __init__(
        self,
        model: str,
        *,
        host: str = "http://localhost:11434",
        timeout: float = 120.0,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.host}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OllamaError(
                f"Ollama HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except (error.URLError, TimeoutError) as exc:
            raise OllamaError(f"unable to reach Ollama at {self.host}: {exc}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OllamaError("Ollama returned invalid JSON") from exc

        message = data.get("message")
        if not isinstance(message, dict):
            raise OllamaError("Ollama response did not contain a message object")

        calls: list[ToolCall] = []
        raw_calls = message.get("tool_calls") or []
        if not isinstance(raw_calls, list):
            raise OllamaError("Ollama message.tool_calls must be a list")

        for index, raw_call in enumerate(raw_calls):
            if not isinstance(raw_call, dict):
                raise OllamaError("Ollama returned a malformed tool call")
            function = raw_call.get("function")
            if not isinstance(function, dict):
                raise OllamaError("Ollama tool call is missing function")
            name = function.get("name")
            arguments = function.get("arguments", {})
            if not isinstance(name, str) or not name.strip():
                raise OllamaError("Ollama tool call is missing a function name")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError as exc:
                    raise OllamaError(
                        f"Ollama returned invalid arguments for {name}"
                    ) from exc
            if not isinstance(arguments, dict):
                raise OllamaError(f"Ollama arguments for {name} must be an object")
            calls.append(
                ToolCall(
                    name=name,
                    arguments=arguments,
                    call_id=str(raw_call.get("id"))
                    if raw_call.get("id")
                    else str(index),
                )
            )

        content = message.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        return LLMResponse(tool_calls=tuple(calls), content=content)

    def check(self) -> None:
        """Perform a real connectivity/model check against Ollama."""
        req = request.Request(f"{self.host}/api/tags", method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (
            error.HTTPError,
            error.URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            raise OllamaError(f"Ollama health check failed: {exc}") from exc

        models = data.get("models", [])
        names = {
            item.get("name")
            for item in models
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        if self.model not in names:
            raise OllamaError(
                f"Ollama model {self.model!r} is not installed; available={sorted(names)}"
            )
