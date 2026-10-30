from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from continuum.cli.output import CheckResult, checks, failure, header, info, success
from continuum.failure import (
    FailureSuiteRunner,
    aggregate_failure_results,
    all_failure_cases,
)
from continuum.graph.client import GraphClient, GraphConfig


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M14 failure suite gate")
    parser.add_argument(
        "--failure-type",
        choices=(
            "missing-evidence",
            "multiple-plausible-paths",
            "temporal-contradiction",
            "misleading-document",
        ),
        default=None,
    )
    parser.add_argument("--case", default=None, help="run one exact case id")
    parser.add_argument("--max-hops", type=int, default=6)
    parser.add_argument("--path-limit", type=int, default=25)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6379)
    parser.add_argument("--graph", default="continuum-m14")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "m14")
    return parser.parse_args()


def _normalize_failure_type(value: str) -> str:
    return value.replace("-", "_")


def _select_cases(args: argparse.Namespace):
    cases = all_failure_cases()
    if args.failure_type:
        failure_type = _normalize_failure_type(args.failure_type)
        cases = tuple(case for case in cases if case.failure_type == failure_type)
    if args.case:
        cases = tuple(case for case in cases if case.case_id == args.case)
    if not cases:
        raise ValueError("no M14 failure case matched the requested selection")
    return cases


def run() -> int:
    args = _args()
    header(
        "M14", "Failure suite · evidence, ambiguity, temporal, misleading-source gates"
    )

    try:
        if args.max_hops < 1 or args.path_limit < 1 or args.top_k < 1:
            raise ValueError("--max-hops, --path-limit, and --top-k must be >= 1")

        cases = _select_cases(args)

        graph = GraphClient(
            GraphConfig(host=args.host, port=args.port, graph_name=args.graph)
        )
        graph.ping()

        runner = FailureSuiteRunner(
            graph,
            max_hops=args.max_hops,
            path_limit=args.path_limit,
            top_k=args.top_k,
        )
        results = runner.run_all(cases)

        for case in cases:
            case.write_json(
                args.output / "cases" / case.failure_type / f"{case.case_id}.json"
            )
        for result in results:
            result.write_json(
                args.output / "runs" / result.failure_type / f"{result.case_id}.json"
            )

        summary = aggregate_failure_results(results)
        summary.update(
            {
                "methodology": {
                    "fixture_truth": "declared by M14 fixture; never generated from Continuum",
                    "investigation": "real Investigator over FalkorDB",
                    "validation": "existing M9 EvidenceValidator",
                    "temporal_validation": "existing M5 temporal validation",
                    "hypothesis_competition": "existing M10 deterministic ranker",
                    "misleading_document_check": "retrieval may surface the document; graph validation decides relationship support",
                    "max_hops": args.max_hops,
                    "path_limit": args.path_limit,
                    "top_k": args.top_k,
                }
            }
        )
        args.output.mkdir(parents=True, exist_ok=True)
        summary_path = args.output / "summary.json"
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
        )

        info("Cases", str(len(results)))
        info("Passed", str(summary["passed_cases"]))
        info("Failed", str(summary["failed_cases"]))
        info("Summary", str(summary_path))

        check_items = [
            CheckResult(
                result.case_id,
                "PASS · expected failure behavior reproduced"
                if result.validation_passed
                else (
                    "FAIL · "
                    f"expected={result.expected_behavior!r}; "
                    f"actual={result.actual_behavior!r}"
                ),
            )
            for result in results
        ]
        check_items.extend(
            [
                CheckResult(
                    "FalkorDB integration",
                    "PASS · graph ping and real graph execution completed",
                ),
                CheckResult(
                    "Persisted results",
                    "PASS · fixture JSON, per-case execution JSON, aggregate summary",
                ),
                CheckResult(
                    "Aggregate calculation",
                    "PASS · counts derived from executed result records",
                ),
            ]
        )
        checks(check_items)

        if not summary["all_cases_passed"]:
            failure("M14")
            return 1

        success("M14")
        return 0
    except (AssertionError, OSError, RuntimeError, TypeError, ValueError) as exc:
        failure(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
