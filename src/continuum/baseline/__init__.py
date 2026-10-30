"""Retrieval-only M12 baseline.

This package is intentionally independent of the investigation engine and
FalkorDB. It consumes a World data adapter, builds a vector retrieval corpus,
and optionally sends the retrieved context to an LLM.
"""

from continuum.baseline.corpus import BaselineCorpus, CorpusDocument, build_corpus
from continuum.baseline.model import BaselineLLM, OllamaBaselineLLM
from continuum.baseline.retrieval import RetrievalResult, TfidfVectorIndex
from continuum.baseline.runner import BaselineResult, BaselineRunner

__all__ = [
    "BaselineCorpus",
    "BaselineLLM",
    "BaselineResult",
    "BaselineRunner",
    "CorpusDocument",
    "OllamaBaselineLLM",
    "RetrievalResult",
    "TfidfVectorIndex",
    "build_corpus",
]
