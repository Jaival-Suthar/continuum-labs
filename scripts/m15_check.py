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
from continuum.core import Hypothesis, InvestigationResult
from continuum.graph.client import GraphClient, GraphConfig
from continuum.graph.loader import WorldLoader
from continuum.hypothesis.model import path_id
from continuum.investigator import Investigator
from domains.software.world import SOFTWARE_WORLD
from domains.supply_chain.world import SUPPLY_CHAIN_WORLD

QUESTION = "Why was Customer X affected?"

PRIMARY_PATH = (
    "supplier-001",
    "component-001",
    "factory-001",
    "shipment-001",
    "warehouse-001",
    "account-001",
    "impact-001",
)

ALTERNATIVE_PATH = (
    "supplier-002",
    "component-002",
    "factory-002",
    "shipment-002",
    "warehouse-001",
    "account-001",
    "impact-001",
)

CONFLICT_PATH = (
    "supplier-003",
    "component-003",
    "factory-003",
    "shipment-003",
    "warehouse-001",
    "account-001",
    "impact-001",
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="M15 supply-chain domain-transfer gate"
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6379)
    parser.add_argument("--graph", default="continuum-m15")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "m15",
    )
    return parser.parse_args()


def _find_path(paths, expected_node_ids):
    for path in paths:
        if path.node_ids == expected_node_ids:
            return path

    raise AssertionError(f"Expected path not found: {expected_node_ids}")


def run() -> int:
    args = _args()

    header(
        "M15",
        "Supply-chain world · domain-transfer gate",
    )

    try:
        # ------------------------------------------------------------------
        # 1. Connect to FalkorDB and load the supply-chain world.
        # ------------------------------------------------------------------
        graph = GraphClient(
            GraphConfig(
                host=args.host,
                port=args.port,
                graph_name=args.graph,
            )
        )

        graph.ping()

        WorldLoader(graph).load(
            SUPPLY_CHAIN_WORLD,
            reset=True,
        )

        # ------------------------------------------------------------------
        # 2. Run the unchanged universal Investigator.
        # ------------------------------------------------------------------
        investigator = Investigator(
            graph,
            SUPPLY_CHAIN_WORLD,
        )

        result = investigator.investigate(QUESTION)

        assert result.target == "impact-001", (
            f"Expected impact-001 as target, got {result.target!r}"
        )

        # ------------------------------------------------------------------
        # 3. Verify the primary, alternative, and temporally conflicting
        #    supply-chain explanations.
        # ------------------------------------------------------------------
        primary_paths = investigator.find_paths(
            "supplier-001",
            "impact-001",
            max_hops=6,
            limit=25,
        )

        alternative_paths = investigator.find_paths(
            "supplier-002",
            "impact-001",
            max_hops=6,
            limit=25,
        )

        conflict_paths = investigator.find_paths(
            "supplier-003",
            "impact-001",
            max_hops=6,
            limit=25,
        )

        primary = _find_path(
            primary_paths,
            PRIMARY_PATH,
        )

        alternative = _find_path(
            alternative_paths,
            ALTERNATIVE_PATH,
        )

        conflict = _find_path(
            conflict_paths,
            CONFLICT_PATH,
        )

        # Primary and alternative explanations must both be temporally valid.
        assert primary.temporally_valid is True, (
            f"Primary path is not temporally valid: {primary.temporal_status}"
        )

        assert alternative.temporally_valid is True, (
            f"Alternative path is not temporally valid: {alternative.temporal_status}"
        )

        # The third path intentionally contains the temporal contradiction.
        assert conflict.temporally_valid is False, (
            f"Conflict path was expected to be temporally invalid, "
            f"got {conflict.temporal_status}"
        )

        # Every hop in the two plausible explanations must have provenance.
        assert len(primary.evidence) == 6, (
            f"Expected 6 primary evidence records, got {len(primary.evidence)}"
        )

        assert len(alternative.evidence) == 6, (
            f"Expected 6 alternative evidence records, got {len(alternative.evidence)}"
        )

        # ------------------------------------------------------------------
        # 4. Exercise the existing M10 hypothesis competition layer.
        #
        # IMPORTANT:
        # The hypotheses reference path_id(p)/path_id(a), and the actual
        # paths are first merged into InvestigationState. This is required
        # because HypothesisEvaluator resolves candidate_path_ids against
        # state.candidate_paths.
        # ------------------------------------------------------------------
        state = investigator.start_investigation(
            QUESTION,
            target_id="impact-001",
        )

        state.merge_result(
            InvestigationResult(
                question=QUESTION,
                target="impact-001",
                candidate_paths=[
                    primary,
                    alternative,
                ],
            ),
            operation="find_paths",
        )

        primary_path_id = path_id(primary)
        alternative_path_id = path_id(alternative)

        assert primary_path_id in {path_id(path) for path in state.candidate_paths}, (
            "Primary path was not added to investigation state"
        )

        assert alternative_path_id in {
            path_id(path) for path in state.candidate_paths
        }, "Alternative path was not added to investigation state"

        state.add_hypothesis(
            Hypothesis(
                id="H1",
                description="Primary supplier chain",
                candidate_path_ids=(primary_path_id,),
                evidence_ids=tuple(evidence.id for evidence in primary.evidence),
            )
        )

        state.add_hypothesis(
            Hypothesis(
                id="H2",
                description="Alternative supplier chain",
                candidate_path_ids=(alternative_path_id,),
                evidence_ids=tuple(evidence.id for evidence in alternative.evidence),
            )
        )

        competition = investigator.compete_hypotheses(state)

        assert competition.outcome == "AMBIGUOUS", (
            "Expected competing primary and alternative explanations "
            f"to remain ambiguous, got {competition.outcome!r}"
        )

        assert set(competition.winner_ids) == {"H1", "H2"}, (
            "Expected both valid explanations to remain tied as plausible "
            f"leaders, got {competition.winner_ids!r}"
        )

        # ------------------------------------------------------------------
        # 5. Domain-transfer proof.
        #
        # The same Investigator implementation is instantiated for both
        # software and supply-chain worlds.
        # ------------------------------------------------------------------
        software_investigator = Investigator(
            graph,
            SOFTWARE_WORLD,
        )

        assert type(software_investigator) is type(investigator), (
            "Supply-chain world requires a different Investigator class"
        )

        # ------------------------------------------------------------------
        # 6. Persist machine-readable M15 summary.
        # ------------------------------------------------------------------
        summary = {
            "question": QUESTION,
            "target": result.target,
            "primary_path": list(primary.node_ids),
            "alternative_path": list(alternative.node_ids),
            "conflict_path": list(conflict.node_ids),
            "primary_hops": primary.hop_count,
            "alternative_hops": alternative.hop_count,
            "conflict_temporal_status": conflict.temporal_status,
            "primary_temporally_valid": primary.temporally_valid,
            "alternative_temporally_valid": alternative.temporally_valid,
            "conflict_temporally_valid": conflict.temporally_valid,
            "primary_evidence_count": len(primary.evidence),
            "alternative_evidence_count": len(alternative.evidence),
            "hypothesis_outcome": competition.outcome,
            "hypothesis_winner_ids": list(competition.winner_ids),
            "same_investigator_class": (
                type(software_investigator).__name__ == type(investigator).__name__
            ),
        }

        args.output.mkdir(
            parents=True,
            exist_ok=True,
        )

        (args.output / "summary.json").write_text(
            json.dumps(
                summary,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        # ------------------------------------------------------------------
        # 7. Human-readable gate output.
        # ------------------------------------------------------------------
        info("Target", str(result.target))
        info("Primary path", str(primary.node_ids))
        info("Alternative path", str(alternative.node_ids))
        info("Conflict", conflict.temporal_status)
        info("Hypotheses", competition.outcome)

        checks(
            [
                CheckResult(
                    "Universal Investigator",
                    "PASS · same Investigator class used for "
                    "software and supply-chain worlds",
                ),
                CheckResult(
                    "Primary path",
                    "PASS · six hops, fully evidenced, temporally valid",
                ),
                CheckResult(
                    "Alternative path",
                    "PASS · independent six-hop explanation remains plausible",
                ),
                CheckResult(
                    "Temporal contradiction",
                    "PASS · contradictory path rejected",
                ),
                CheckResult(
                    "Hypothesis competition",
                    "PASS · ambiguity preserved between two valid explanations",
                ),
            ]
        )

        success("M15")
        return 0

    except (
        AssertionError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        failure(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
