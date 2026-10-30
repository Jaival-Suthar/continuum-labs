from __future__ import annotations

import json
from pathlib import Path

import pytest

from continuum.baseline import BaselineRunner, build_corpus
from domains.software.world import SOFTWARE_WORLD


class StubLLM:
    model = "test-model"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, question: str, context: tuple[str, ...]) -> str:
        self.calls += 1
        assert question == "Why did incident-001 happen?"
        assert context
        return "Insufficient evidence."


def test_corpus_contains_same_world_nodes_and_edges_without_graph_access():
    corpus = build_corpus(SOFTWARE_WORLD)

    assert corpus.world_name == "software"
    assert len(corpus.documents) == len(SOFTWARE_WORLD.data.nodes()) + len(
        SOFTWARE_WORLD.data.edges()
    )
    assert any(doc.id == "node:incident-001" for doc in corpus.documents)
    assert any(
        doc.metadata["kind"] == "edge"
        and doc.metadata["source_id"] == "metric-001"
        and doc.metadata["target_id"] == "incident-001"
        for doc in corpus.documents
    )


def test_retrieval_is_vector_based_deterministic_and_ranks_incident_context():
    runner = BaselineRunner(build_corpus(SOFTWARE_WORLD))

    first = runner.retrieve("Why did incident-001 happen?", top_k=8)
    second = runner.retrieve("Why did incident-001 happen?", top_k=8)

    assert [item.document.id for item in first] == [item.document.id for item in second]
    assert [item.score for item in first] == [item.score for item in second]
    assert first[0].score > 0.0
    assert any("incident-001" in item.document.text for item in first)
    assert all(0.0 <= item.score <= 1.0 for item in first)


def test_runner_captures_structured_result_and_real_llm_boundary(tmp_path: Path):
    llm = StubLLM()
    runner = BaselineRunner(build_corpus(SOFTWARE_WORLD), llm=llm)

    result = runner.run("Why did incident-001 happen?", top_k=5)

    assert llm.calls == 1
    assert result.answer == "Insufficient evidence."
    assert result.model == "test-model"
    assert result.retrieved_ids
    assert result.retrieved_source_ids
    assert len(result.retrieved_context) == 5

    path = result.write_json(tmp_path / "result.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["question"] == result.question
    assert payload["retrieved_ids"] == list(result.retrieved_ids)
    assert payload["answer"] == result.answer


def test_answer_requires_a_real_provider():
    runner = BaselineRunner(build_corpus(SOFTWARE_WORLD))

    with pytest.raises(ValueError, match="LLM provider"):
        runner.run("Why did incident-001 happen?", answer=True)


def test_retrieval_validates_inputs():
    runner = BaselineRunner(build_corpus(SOFTWARE_WORLD))

    with pytest.raises(ValueError, match="query"):
        runner.retrieve("")

    with pytest.raises(ValueError, match="top_k"):
        runner.retrieve("incident-001", top_k=0)


def test_baseline_modules_have_no_investigation_or_falkordb_imports():
    import ast
    from pathlib import Path

    baseline_dir = (
        Path(__file__).resolve().parents[1] / "src" / "continuum" / "baseline"
    )
    forbidden = {"continuum.investigator", "continuum.graph", "falkordb"}

    for path in baseline_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {node.module or ""}
            else:
                continue
            assert names.isdisjoint(forbidden), f"forbidden import in {path}: {names}"
