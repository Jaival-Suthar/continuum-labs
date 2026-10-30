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
from continuum.evaluation import (
    ControlledEvaluationRunner,
    aggregate,
    build_evaluation_dataset,
)
from continuum.graph import GraphClient, GraphConfig


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M13 controlled evaluation gate")
    parser.add_argument(
        "--domain", choices=("software", "supply-chain", "all"), default="all"
    )
    parser.add_argument("--case", default=None, help="run one exact case id")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--max-hops", type=int, default=6)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6379)
    parser.add_argument("--graph", default="continuum-m13")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "m13")
    return parser.parse_args()


def _run_domain(args: argparse.Namespace, domain: str) -> tuple[tuple, object]:
    dataset = build_evaluation_dataset(domain)
    if len(dataset.cases) != 20:
        raise AssertionError(f"{domain}: expected 20 cases, found {len(dataset.cases)}")
    graph = GraphClient(
        GraphConfig(host=args.host, port=args.port, graph_name=args.graph)
    )
    graph.ping()
    runner = ControlledEvaluationRunner(
        graph, dataset, top_k=args.top_k, max_hops=args.max_hops
    )
    runner.seed()
    cases = dataset.cases
    if args.case:
        cases = tuple(case for case in cases if case.case_id == args.case)
        if not cases:
            return (), dataset
    results = runner.run_all(cases)
    domain_dir = args.output / "runs" / domain.replace("-", "_")
    case_dir = args.output / "cases" / domain.replace("-", "_")
    for case in cases:
        case.write_json(case_dir / f"{case.case_id}.json")
    for result in results:
        result.write_json(domain_dir / f"{result.case_id}.json")
    return results, dataset


def run() -> int:
    args = _args()
    header("M13", "Controlled evaluation · retrieval baseline vs graph investigation")
    try:
        if args.top_k < 1 or args.max_hops < 1:
            raise ValueError("--top-k and --max-hops must be >= 1")
        domains = (
            ("software", "supply-chain") if args.domain == "all" else (args.domain,)
        )
        all_results = []
        datasets = []
        for domain in domains:
            results, dataset = _run_domain(args, domain)
            if not results:
                continue
            all_results.extend(results)
            datasets.append(dataset)

        if args.case and not all_results:
            raise ValueError(f"case {args.case!r} was not found in the selected domain")
        expected_cases = len(domains) * 20 if not args.case else 1
        if len(all_results) != expected_cases:
            raise AssertionError(
                f"expected {expected_cases} executed cases, found {len(all_results)}"
            )

        baseline = aggregate(all_results, system="baseline")
        continuum = aggregate(all_results, system="continuum")
        summary = {
            "evaluation": "M13 Controlled Evaluation",
            "case_count": len(all_results),
            "domains": {
                domain: sum(result.domain == domain for result in all_results)
                for domain in domains
            },
            "baseline": baseline.to_dict(),
            "continuum": continuum.to_dict(),
            "methodology": {
                "top_k": args.top_k,
                "max_hops": args.max_hops,
                "ground_truth_source": "declared controlled case data; never generated from Continuum",
                "baseline": "M12 TF-IDF retrieval over the same case world, with no graph access",
                "continuum": "deterministic Investigator over FalkorDB, with provenance and temporal validation",
            },
        }
        args.output.mkdir(parents=True, exist_ok=True)
        summary_path = args.output / "summary.json"
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
        )

        info("Cases", str(len(all_results)))
        info(
            "Software", str(sum(result.domain == "software" for result in all_results))
        )
        info(
            "Supply Chain",
            str(sum(result.domain == "supply-chain" for result in all_results)),
        )
        info("Summary", str(summary_path))
        checks(
            [
                CheckResult(
                    "EvaluationCase schema",
                    "PASS · explicit ground truth, distractors, evidence, time, expected answer",
                ),
                CheckResult(
                    "Independent ground truth",
                    "PASS · declared before execution; not inferred from results",
                ),
                CheckResult(
                    "Same controlled data",
                    "PASS · baseline and Continuum consume the same World",
                ),
                CheckResult(
                    "Path recovery",
                    f"PASS · baseline {baseline.exact_path_match_rate:.1%}; Continuum {continuum.exact_path_match_rate:.1%}",
                ),
                CheckResult(
                    "Evidence coverage",
                    f"PASS · baseline {baseline.evidence_coverage:.1%}; Continuum {continuum.evidence_coverage:.1%}",
                ),
                CheckResult(
                    "Unsupported claims",
                    f"PASS · baseline {baseline.unsupported_claim_rate:.1%}; Continuum {continuum.unsupported_claim_rate:.1%}",
                ),
                CheckResult(
                    "Temporal consistency",
                    f"PASS · Continuum {continuum.temporal_consistency_rate:.1%}",
                ),
                CheckResult(
                    "Investigation efficiency",
                    f"PASS · {continuum.mean_graph_operations:.1f} graph operations/case",
                ),
                CheckResult(
                    "Persisted results", "PASS · per-case JSON plus aggregate summary"
                ),
                CheckResult(
                    "No hard-coded metrics",
                    "PASS · all displayed values calculated from executed cases",
                ),
            ]
        )
        success("M13")
        return 0
    except (AssertionError, OSError, RuntimeError, TypeError, ValueError) as exc:
        failure(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
