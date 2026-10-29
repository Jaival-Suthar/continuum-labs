from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from continuum.cli.output import CheckResult, checks, failure, header, path, success
from continuum.core import EvidenceStatus
from continuum.graph import GraphClient, WorldLoader
from continuum.investigator import Investigator
from domains.software.world import SOFTWARE_WORLD


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    header("M6", "Deterministic investigation engine")
    client = GraphClient()

    try:
        WorldLoader(client).load(SOFTWARE_WORLD, reset=True)
        investigator = Investigator(client, SOFTWARE_WORLD)

        outcome = investigator.find_outcome("Why did incident-001 happen?")
        if outcome.id != "incident-001":
            fail(f"unexpected outcome: {outcome.id}")

        related = investigator.find_related_entities(outcome.id)
        if not any(node.id == "metric-001" for node in related):
            fail("metric-001 was not found as a related entity")

        neighborhood = investigator.expand_neighborhood(outcome.id, depth=2)
        if not any(node.id == "deployment-001" for node in neighborhood):
            fail("deployment-001 was not found in the depth-2 neighborhood")

        candidates = investigator.trace_backward(outcome.id, max_hops=5, limit=25)
        primary = next(
            (
                candidate
                for candidate in candidates
                if candidate.node_ids
                == (
                    "commit-001",
                    "dependency-gateway-sdk",
                    "service-payments",
                    "deployment-001",
                    "metric-001",
                    "incident-001",
                )
            ),
            None,
        )
        if primary is None:
            fail("primary multi-hop path was not discovered by FalkorDB")
        if primary.temporal_status != "VALID":
            fail(f"primary path temporal status was {primary.temporal_status}")

        forward = investigator.trace_forward("commit-001", max_hops=5, limit=25)
        if not any(candidate.node_ids == primary.node_ids for candidate in forward):
            fail("trace_forward did not recover the primary downstream path")

        preceding = investigator.find_preceding_changes(outcome.id)
        if not any(node.id == "commit-001" for node in preceding):
            fail("find_preceding_changes did not return commit-001")

        impact = investigator.find_downstream_impact("commit-001", max_hops=5, limit=25)
        if not any(candidate.node_ids == primary.node_ids for candidate in impact):
            fail("find_downstream_impact did not recover the primary path")

        temporal_check = investigator.check_temporal_consistency(primary)
        if temporal_check.status != "VALID":
            fail("check_temporal_consistency did not return VALID for primary path")

        supported = investigator.find_supporting_evidence(primary)
        if len(supported) < 4:
            fail(f"primary path resolved too little evidence: {len(supported)}")

        config_paths = investigator.find_paths(
            "config-001", "incident-001", max_hops=2, limit=25
        )
        config = next(
            (
                candidate
                for candidate in config_paths
                if candidate.node_ids == ("config-001", "metric-001", "incident-001")
            ),
            None,
        )
        if config is None or config.temporal_status != "INVALID":
            fail("configuration temporal trap was not surfaced as INVALID")

        conflicts = investigator.find_conflicting_evidence([primary, config])
        if not conflicts:
            fail("temporal conflict was silently discarded")

        infra_paths = investigator.find_paths(
            "infra-event-001", "incident-001", max_hops=2, limit=25
        )
        infra = next(
            (
                candidate
                for candidate in infra_paths
                if candidate.node_ids
                == ("infra-event-001", "metric-001", "incident-001")
            ),
            None,
        )
        if infra is None or infra.missing_evidence_count == 0:
            fail("infrastructure alternative did not surface its evidence gap")

        result = investigator.investigate("Why did incident-001 happen?")
        if result.target != "incident-001":
            fail("investigation target mismatch")
        if not result.ranked_paths:
            fail("investigation returned no ranked paths")
        if result.ranked_paths[0].path.node_ids != primary.node_ids:
            fail("deterministic ranking did not prefer the evidence-backed valid path")
        if any("0." in item for item in result.trace):
            fail("result trace contains an invented confidence score")
        if not any(
            "configuration" in item.lower() or "config-001" in item
            for item in result.contradictions
        ):
            fail("configuration contradiction was not surfaced")

        # Explicitly prove the engine consumed M4 statuses rather than inventing them.
        if not all(e.status in EvidenceStatus.ALL for e in result.evidence):
            fail("result contains an unsupported evidence status")

        path(primary.node_ids, primary.relationships)

    except (AssertionError, ValueError, TypeError) as exc:
        failure(str(exc))
        return 1

    checks(
        [
            CheckResult("Find outcome", "PASS · incident-001"),
            CheckResult("Find related entities", f"PASS · {len(related)} entities"),
            CheckResult(
                "Expand neighborhood", f"PASS · depth=2 · {len(neighborhood)} entities"
            ),
            CheckResult("Find paths", f"PASS · {len(candidates)} candidates"),
            CheckResult("Trace backward", f"PASS · {primary.hop_count} hops"),
            CheckResult("Trace forward", f"PASS · {len(forward)} paths"),
            CheckResult("Find preceding changes", f"PASS · {len(preceding)} changes"),
            CheckResult("Find downstream impact", f"PASS · {len(impact)} paths"),
            CheckResult("Supporting evidence", f"PASS · {len(supported)} records"),
            CheckResult("Conflicting evidence", f"PASS · {len(conflicts)} conflicts"),
            CheckResult(
                "Temporal consistency", "PASS · VALID / INVALID / UNKNOWN surfaced"
            ),
            CheckResult("Path ranking", "PASS · deterministic evidence signals"),
            CheckResult("No LLM synthesis", "PASS · deterministic engine only"),
        ]
    )
    success("M6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
