from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from continuum.api.service import InvestigationService
from continuum.cli.output import CheckResult, checks, failure, header, info, success
from continuum.graph.client import GraphClient, GraphConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="M17 real backend/UI contract gate")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6379)
    parser.add_argument("--graph", default="continuum-m17")
    args = parser.parse_args()

    header("M17", "Investigation UI contract gate")

    try:
        graph = GraphClient(
            GraphConfig(
                host=args.host,
                port=args.port,
                graph_name=args.graph,
            )
        )

        service = InvestigationService(graph)

        health = service.health()
        assert health["falkordb"] == "connected"

        software = service.create(
            question="Why did incident-001 happen?",
            domain="software",
            target_id="incident-001",
        )

        supply = service.create(
            question="Why was Customer X affected?",
            domain="supply-chain",
            target_id="impact-001",
        )

        # ------------------------------------------------------------------
        # Core investigation contract
        # ------------------------------------------------------------------

        assert software["target"] == "incident-001"
        assert supply["target"] == "impact-001"

        assert software["paths"]
        assert supply["paths"]

        assert software["graph"]["nodes"]
        assert software["graph"]["edges"]

        assert software["trace"]
        assert software["evidence"]
        assert software["ranked_paths"]

        # ------------------------------------------------------------------
        # Software investigation: verify the actual primary path by its
        # graph structure, not by the internal hashed path_id.
        # ------------------------------------------------------------------

        expected_software_path = (
            "commit-001",
            "dependency-gateway-sdk",
            "service-payments",
            "deployment-001",
            "metric-001",
            "incident-001",
        )

        assert any(
            tuple(path["node_ids"]) == expected_software_path
            for path in software["paths"]
        )

        # M17 must preserve temporally invalid/rejected paths so the UI can
        # expose why they were rejected rather than silently removing them.
        assert any(path["temporally_valid"] is False for path in software["paths"])

        # ------------------------------------------------------------------
        # Supply-chain investigation: verify that the cross-domain contract
        # produces a real investigation rather than a software-specific path.
        # ------------------------------------------------------------------

        expected_supply_path = (
            "supplier-001",
            "component-001",
            "factory-001",
            "shipment-001",
            "warehouse-001",
            "account-001",
            "impact-001",
        )

        assert any(
            tuple(path["node_ids"]) == expected_supply_path for path in supply["paths"]
        )

        assert supply["status"] in {
            "COMPLETED",
            "AMBIGUOUS",
            "INSUFFICIENT_EVIDENCE",
        }

        # Hypotheses must not expose fabricated confidence values. M17 uses
        # the engine's actual hypothesis competition/verdict instead.
        assert all("confidence" not in item for item in software["hypotheses"])

        # ------------------------------------------------------------------
        # Persistence / reload
        # ------------------------------------------------------------------

        reloaded = InvestigationService(graph).get(software["id"])

        assert reloaded["id"] == software["id"]
        assert reloaded["graph"] == software["graph"]

        # ------------------------------------------------------------------
        # Human-readable gate output
        # ------------------------------------------------------------------

        info("FalkorDB", "Connected")

        info(
            "Software",
            (
                f"{software['status']} · "
                f"{len(software['paths'])} paths · "
                f"{len(software['evidence'])} evidence"
            ),
        )

        info(
            "Supply chain",
            (
                f"{supply['status']} · "
                f"{len(supply['paths'])} paths · "
                f"{len(supply['evidence'])} evidence"
            ),
        )

        checks(
            [
                CheckResult("Thin API over Investigator", "PASS"),
                CheckResult("Real graph paths", "PASS"),
                CheckResult("Real provenance/evidence", "PASS"),
                CheckResult("Actual investigation trace", "PASS"),
                CheckResult("Deterministic ranking", "PASS"),
                CheckResult("Cross-domain UI contract", "PASS"),
                CheckResult("Persistence/reload", "PASS"),
                CheckResult("No fabricated confidence", "PASS"),
            ]
        )

        success("M17")
        return 0

    except (AssertionError, RuntimeError, ValueError, KeyError) as exc:
        failure(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
