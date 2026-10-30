from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from continuum.baseline.corpus import BaselineCorpus
from continuum.baseline.model import BaselineLLM
from continuum.baseline.retrieval import RetrievalResult, TfidfVectorIndex


@dataclass(frozen=True)
class BaselineResult:
    """Machine-readable M12 result for later controlled evaluation."""

    question: str
    world: str
    top_k: int
    retrieved_ids: tuple[str, ...]
    retrieved_source_ids: tuple[str, ...]
    retrieved_context: tuple[str, ...]
    retrieval_scores: tuple[float, ...]
    answer: str | None
    model: str | None
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    def write_json(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return destination


class BaselineRunner:
    """Retrieval → optional LLM answer pipeline, with no investigation calls."""

    def __init__(
        self,
        corpus: BaselineCorpus,
        *,
        llm: BaselineLLM | None = None,
    ) -> None:
        self.corpus = corpus
        self.index = TfidfVectorIndex(corpus)
        self.llm = llm

    def retrieve(self, question: str, *, top_k: int = 5) -> tuple[RetrievalResult, ...]:
        return self.index.search(question, top_k=top_k)

    def run(
        self,
        question: str,
        *,
        top_k: int = 5,
        answer: bool = True,
    ) -> BaselineResult:
        if not question.strip():
            raise ValueError("question must not be empty")
        if answer and self.llm is None:
            raise ValueError("answer=True requires an LLM provider")

        retrieved = self.retrieve(question, top_k=top_k)
        context = tuple(item.document.text for item in retrieved)
        source_ids = tuple(
            dict.fromkeys(
                source_id
                for item in retrieved
                for source_id in item.document.source_ids
            )
        )

        generated = None
        model = None
        if answer:
            generated = self.llm.generate(question, context)
            model = getattr(self.llm, "model", type(self.llm).__name__)

        return BaselineResult(
            question=question,
            world=self.corpus.world_name,
            top_k=top_k,
            retrieved_ids=tuple(item.document.id for item in retrieved),
            retrieved_source_ids=source_ids,
            retrieved_context=context,
            retrieval_scores=tuple(item.score for item in retrieved),
            answer=generated,
            model=model,
            created_at=datetime.now(UTC).isoformat(),
        )
