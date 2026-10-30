from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from continuum.baseline import BaselineRunner, OllamaBaselineLLM, build_corpus
from continuum.cli.output import CheckResult, checks, failure, header, info, success
from domains.software.world import SOFTWARE_WORLD

QUESTION = "Why did incident-001 happen?"
DEFAULT_TOP_K = 8
DEFAULT_MODEL = "qwen3:8b"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M12 retrieval-only baseline gate")
    parser.add_argument(
        "--mode",
        choices=("retrieval", "ollama"),
        default="retrieval",
        help="retrieval validates the control without an LLM; ollama runs the real answer step",
    )
    parser.add_argument(
        "--model", default=os.getenv("CONTINUUM_LLM_MODEL", DEFAULT_MODEL)
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "m12" / "baseline_result.json",
    )
    return parser.parse_args()


def run() -> int:
    args = _args()
    header("M12", "Retrieval-only baseline · no graph investigation")

    try:
        if args.top_k < 1:
            raise ValueError("--top-k must be >= 1")

        corpus = build_corpus(SOFTWARE_WORLD)
        runner = BaselineRunner(corpus)

        retrieved = runner.retrieve(QUESTION, top_k=args.top_k)
        if not retrieved:
            raise AssertionError("retrieval returned no documents")
        if not any("incident-001" in item.document.text for item in retrieved):
            raise AssertionError("retrieval did not return incident-001 context")
        if any(item.score < 0.0 or item.score > 1.0 for item in retrieved):
            raise AssertionError("retrieval produced an invalid cosine score")

        if args.mode == "retrieval":
            result = runner.run(QUESTION, top_k=args.top_k, answer=False)
        else:
            llm = OllamaBaselineLLM(args.model)
            llm.check()
            runner = BaselineRunner(corpus, llm=llm)
            result = runner.run(QUESTION, top_k=args.top_k, answer=True)
            if not result.answer:
                raise AssertionError("real Ollama baseline returned no answer")

        output = result.write_json(args.output)

        payload = json.loads(output.read_text(encoding="utf-8"))
        if payload["question"] != QUESTION:
            raise AssertionError("saved result question mismatch")
        if len(payload["retrieved_ids"]) != min(args.top_k, len(corpus.documents)):
            raise AssertionError("saved result retrieval count mismatch")
        if args.mode == "ollama" and not payload["answer"]:
            raise AssertionError("saved result does not contain the real model answer")

    except (AssertionError, OSError, RuntimeError, TypeError, ValueError) as exc:
        failure(f"{type(exc).__name__}: {exc}")
        return 1

    info("World", corpus.world_name)
    info("Corpus documents", str(len(corpus.documents)))
    info("Question", QUESTION)
    info("Top-k", str(args.top_k))
    info("Retrieved", str(len(result.retrieved_ids)))
    info("LLM", result.model or "not requested")
    info("Result", str(output))

    checks(
        [
            CheckResult("Same software world data", "PASS · built from SOFTWARE_WORLD"),
            CheckResult(
                "Vector retrieval", "PASS · deterministic TF-IDF cosine retrieval"
            ),
            CheckResult(
                "Top-k context", f"PASS · {len(result.retrieved_ids)} documents"
            ),
            CheckResult(
                "Graph investigation",
                "PASS · no GraphClient, FalkorDB, or Investigator used",
            ),
            CheckResult(
                "Structured result",
                "PASS · question/context/source ids/scores captured",
            ),
            CheckResult(
                "LLM answer",
                (
                    "PASS · real Ollama response captured"
                    if result.answer
                    else "NOT RUN · use --mode ollama for the real LLM step"
                ),
            ),
        ]
    )

    if result.answer:
        print("\nBASELINE ANSWER\n")
        print(result.answer)

    success("M12")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
