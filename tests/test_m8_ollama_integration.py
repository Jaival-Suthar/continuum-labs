from __future__ import annotations

import os

import pytest

from continuum.agent import OllamaProvider


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("CONTINUUM_RUN_OLLAMA_TEST") != "1",
    reason="set CONTINUUM_RUN_OLLAMA_TEST=1 to run the real local Ollama integration",
)
def test_real_ollama_provider():
    model = os.getenv("CONTINUUM_OLLAMA_MODEL", "qwen3:30b-a3b-instruct-2507-q4_K_M")
    provider = OllamaProvider(model)
    provider.check()
    response = provider.chat(
        [{"role": "user", "content": "Respond with exactly DONE."}],
        tools=[],
    )
    assert response.content.strip().rstrip(".!") == "DONE"
