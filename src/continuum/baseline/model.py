from __future__ import annotations

import json
from typing import Any, Protocol
from urllib import error, request


class BaselineLLM(Protocol):
    """Minimal answer-only model boundary for the retrieval baseline."""

    def generate(self, question: str, context: tuple[str, ...]) -> str: ...

    def check(self) -> None: ...


class OllamaBaselineError(RuntimeError):
    """Raised when the real Ollama baseline model cannot be used."""


class OllamaBaselineLLM:
    """Real Ollama chat client with no tool calling or investigation access."""

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

    @staticmethod
    def _prompt(question: str, context: tuple[str, ...]) -> str:
        joined = "\n\n--- RETRIEVED DOCUMENT ---\n\n".join(context)
        return (
            "Answer the question using only the retrieved documents below. "
            "Do not invent facts, relationships, timestamps, sources, or causes. "
            "If the retrieved documents do not support an answer, say "
            '"Insufficient evidence." Explicitly distinguish what is directly '
            "stated from what you infer.\n\n"
            f"QUESTION:\n{question}\n\n"
            f"RETRIEVED DOCUMENTS:\n{joined}"
        )

    def generate(self, question: str, context: tuple[str, ...]) -> str:
        if not question.strip():
            raise ValueError("question must not be empty")
        if not context:
            raise ValueError("context must not be empty")

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are the answerer for a retrieval-only baseline. "
                    "You have no graph tools and no access to external knowledge."
                ),
            },
            {
                "role": "user",
                "content": self._prompt(question, context),
            },
        ]
        payload = {
            "model": self.model,
            "messages": messages,
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
            raise OllamaBaselineError(
                f"Ollama HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except (error.URLError, TimeoutError) as exc:
            raise OllamaBaselineError(
                f"unable to reach Ollama at {self.host}: {exc}"
            ) from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OllamaBaselineError("Ollama returned invalid JSON") from exc

        message = data.get("message")
        if not isinstance(message, dict):
            raise OllamaBaselineError(
                "Ollama response did not contain a message object"
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OllamaBaselineError(
                "Ollama response did not contain non-empty message content"
            )
        return content.strip()

    def check(self) -> None:
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
            raise OllamaBaselineError(f"Ollama health check failed: {exc}") from exc

        models = data.get("models", [])
        names = {
            item.get("name")
            for item in models
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        if self.model not in names:
            raise OllamaBaselineError(
                f"Ollama model {self.model!r} is not installed; "
                f"available={sorted(names)}"
            )
