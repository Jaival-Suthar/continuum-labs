from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from continuum.baseline.corpus import BaselineCorpus, CorpusDocument

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_:][a-z0-9]+)*", re.IGNORECASE)


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(text.lower()))


@dataclass(frozen=True)
class RetrievalResult:
    document: CorpusDocument
    score: float
    rank: int


class TfidfVectorIndex:
    """Deterministic sparse-vector retrieval over the baseline corpus.

    This is deliberately a real vector-space retrieval method, not a graph
    lookup. It uses TF-IDF weighted term vectors and cosine similarity.
    """

    def __init__(self, corpus: BaselineCorpus):
        self.corpus = corpus
        self._document_tokens = tuple(_tokens(doc.text) for doc in corpus.documents)
        self._idf = self._build_idf(self._document_tokens)
        self._vectors = tuple(self._vector(tokens) for tokens in self._document_tokens)

    @staticmethod
    def _build_idf(
        documents: tuple[tuple[str, ...], ...],
    ) -> dict[str, float]:
        document_frequency: Counter[str] = Counter()
        for tokens in documents:
            document_frequency.update(set(tokens))
        count = len(documents)
        return {
            token: math.log((1 + count) / (1 + frequency)) + 1.0
            for token, frequency in document_frequency.items()
        }

    def _vector(self, tokens: tuple[str, ...]) -> dict[str, float]:
        counts = Counter(tokens)
        total = sum(counts.values())
        if not total:
            return {}
        return {
            token: (frequency / total) * self._idf[token]
            for token, frequency in counts.items()
            if token in self._idf
        }

    @staticmethod
    def _cosine(
        left: dict[str, float],
        right: dict[str, float],
    ) -> float:
        if not left or not right:
            return 0.0
        dot = sum(value * right.get(token, 0.0) for token, value in left.items())
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return dot / (left_norm * right_norm)

    def search(self, query: str, *, top_k: int = 5) -> tuple[RetrievalResult, ...]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be >= 1")

        query_vector = self._vector(_tokens(query))
        scored = [
            (index, self._cosine(query_vector, vector))
            for index, vector in enumerate(self._vectors)
        ]
        scored.sort(key=lambda item: (-item[1], self.corpus.documents[item[0]].id))
        selected = [
            (index, score) for index, score in scored[: min(top_k, len(scored))]
        ]
        return tuple(
            RetrievalResult(
                document=self.corpus.documents[index],
                score=score,
                rank=rank,
            )
            for rank, (index, score) in enumerate(selected, start=1)
        )
