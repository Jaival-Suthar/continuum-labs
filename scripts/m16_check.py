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
from continuum.cross_domain import DomainGateSpec, run_cross_domain_gate
from continuum.graph.client import GraphClient, GraphConfig
from domains.software.world import SOFTWARE_WORLD
from domains.supply_chain.world import SUPPLY_CHAIN_WORLD

SOFTWARE_QUESTION = "Why did incident-001 happen?"
SOFTWARE_PRIMARY_PATH = (
    "commit-001",
    "dependency-gateway-sdk",
    "service-payments",
    "deployment-001",
    "metric-001",
    "incident-001",
)
SOFTWARE_ALTERNATIVE_PATH = (
    "infra-event-001",
    "metric-001",
    "incident-001",
)
SOFTWARE_CONFLICT_PATH = (
    "config-001",
    "metric-001",
    "incident-001",
)

SUPPLY_CHAIN_QUESTION = "Why was Customer X affected?"
SUPPLY_CHAIN_PRIMARY_PATH = (
    "supplier-001",
    "component-001",
    "factory-001",
    "shipment-001",
    "warehouse-001",
    "account-001",
    "impact-001",
)
SUPPLY_CHAIN_ALTERNATIVE_PATH = (
    "supplier-002",
    "component-002",
    "factory-002",
    "shipment-002",
    "warehouse-001",
    "account-001",
    "impact-001",
)
SUPPLY_CHAIN_CONFLICT_PATH = (
    "supplier-003",
    "component-003",
    "factory-003",
    "shipment-003",
    "warehouse-001",
    "account-001",
    "impact-001",
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M16 cross-domain investigation gate")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6379)
    parser.add_argument("--graph", default="continuum-m16")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "m16")
    return parser.parse_args()


def run() -> int:
    args = _args()
    header("M16", "Cross-domain investigation gate")

    try:
        graph = GraphClient(
            GraphConfig(host=args.host, port=args.port, graph_name=args.graph)
        )
        graph.ping()

        gate = run_cross_domain_gate(
            graph,
            software=DomainGateSpec(
                name="software",
                world=SOFTWARE_WORLD,
                question=SOFTWARE_QUESTION,
                target_id="incident-001",
                primary_path=SOFTWARE_PRIMARY_PATH,
                alternative_path=SOFTWARE_ALTERNATIVE_PATH,
                conflict_path=SOFTWARE_CONFLICT_PATH,
            ),
            supply_chain=DomainGateSpec(
                name="supply_chain",
                world=SUPPLY_CHAIN_WORLD,
                question=SUPPLY_CHAIN_QUESTION,
                target_id="impact-001",
                primary_path=SUPPLY_CHAIN_PRIMARY_PATH,
                alternative_path=SUPPLY_CHAIN_ALTERNATIVE_PATH,
                conflict_path=SUPPLY_CHAIN_CONFLICT_PATH,
            ),
        )

        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "software_run.json").write_text(
            json.dumps(gate.as_dict()["software"], indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (args.output / "supply_chain_run.json").write_text(
            json.dumps(gate.as_dict()["supply_chain"], indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (args.output / "cross_domain_summary.json").write_text(
            json.dumps(gate.as_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )

        info("Software target", gate.software.target)
        info("Software primary", " -> ".join(gate.software.primary_path))
        info("Software hypotheses", gate.software.hypothesis.outcome)
        info("Supply-chain target", gate.supply_chain.target)
        info("Supply-chain primary", " -> ".join(gate.supply_chain.primary_path))
        info("Supply-chain hypotheses", gate.supply_chain.hypothesis.outcome)

        checks(
            [
                CheckResult(
                    "Software investigation",
                    "PASS · target, path, evidence and temporal validation",
                ),
                CheckResult(
                    "Supply-chain investigation",
                    "PASS · target, path, evidence and temporal validation",
                ),
                CheckResult(
                    "Shared Investigator",
                    "PASS · one Investigator implementation and instance",
                ),
                CheckResult(
                    "Shared graph operations",
                    "PASS · FalkorDB traversal/temporal layers are shared",
                ),
                CheckResult(
                    "Shared state model", "PASS · InvestigationState is shared"
                ),
                CheckResult(
                    "Shared hypothesis system", "PASS · HypothesisEvaluator is shared"
                ),
                CheckResult("Shared validation", "PASS · EvidenceValidator is shared"),
                CheckResult(
                    "Shared reporting", "PASS · GroundedReportBuilder is shared"
                ),
                CheckResult("No domain-specific Investigator branches", "PASS"),
            ]
        )
        success("M16")
        return 0
    except (AssertionError, OSError, RuntimeError, TypeError, ValueError) as exc:
        failure(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
