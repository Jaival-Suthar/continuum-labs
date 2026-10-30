from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from continuum.agent import AgenticInvestigator, OllamaProvider
from continuum.agent.prompts import state_context
from continuum.cli.output import CheckResult, checks, failure, header, info, success
from continuum.graph import GraphClient, WorldLoader
from continuum.investigator import Investigator
from continuum.validation import Claim, ClaimClassification, EvidenceValidator
from domains.software.world import SOFTWARE_WORLD

CLAIM_PROPOSAL_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_claim",
        "description": (
            "Propose exactly one graph relationship claim for Continuum to "
            "validate. Do not provide a verdict, confidence, evidence status, "
            "or explanation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": (
                        "Existing graph node ID on the left side of the relationship."
                    ),
                    "minLength": 1,
                },
                "relationship": {
                    "type": "string",
                    "description": "The graph relationship type being proposed.",
                    "minLength": 1,
                },
                "object": {
                    "type": "string",
                    "description": (
                        "Existing graph node ID on the right side of the relationship."
                    ),
                    "minLength": 1,
                },
            },
            "required": ["subject", "relationship", "object"],
            "additionalProperties": False,
        },
    },
}


def run_deterministic() -> int:
    """Run the M9 validator gate without FalkorDB or an LLM."""

    class Result:
        def __init__(self, result_set):
            self.result_set = result_set

    class FakeGraph:
        def __init__(
            self,
            *,
            exists=True,
            evidence=True,
            contradiction=False,
            temporal="valid",
        ):
            self.exists = exists
            self.evidence = evidence
            self.contradiction = contradiction
            self.temporal = temporal

        def read(self, cypher, params=None):
            if "MATCH (source {id:$subject})-[r:" in cypher:
                if not self.exists:
                    return Result([])

                status = "CONTRADICTED" if self.contradiction else "OBSERVED"

                return Result(
                    [
                        [
                            "commit-001",
                            "CHANGED",
                            "dependency-001",
                            "edge-001",
                            "2026-08-01T09:00:00Z",
                            None,
                            None,
                            status,
                        ]
                    ]
                )

            if "MATCH (source {id:$source_id})-[r]-(target {id:$target_id})" in cypher:
                if not self.evidence:
                    return Result(
                        [
                            [
                                "commit-001",
                                "CHANGED",
                                "dependency-001",
                                "edge-001",
                                "2026-08-01T09:00:00Z",
                                None,
                                None,
                                "UNKNOWN",
                                [],
                                [],
                                [],
                                [],
                                [],
                                [],
                            ]
                        ]
                    )

                status = "CONTRADICTED" if self.contradiction else "OBSERVED"

                return Result(
                    [
                        [
                            "commit-001",
                            "CHANGED",
                            "dependency-001",
                            "edge-001",
                            "2026-08-01T09:00:00Z",
                            None,
                            None,
                            "OBSERVED",
                            ["source-001"],
                            [status],
                            ["2026-08-01T09:05:00Z"],
                            ["record-001"],
                            ["span-1"],
                            ["source one"],
                        ]
                    ]
                )

            if "MATCH (subject {id:$subject}), (object {id:$object})" in cypher:
                subject_time = (
                    "2026-08-01T10:30:00Z"
                    if self.temporal == "invalid"
                    else "2026-08-01T09:00:00Z"
                )

                return Result(
                    [
                        [
                            "commit-001",
                            {"id": "commit-001", "timestamp": subject_time},
                            "dependency-001",
                            {"id": "dependency-001"},
                        ]
                    ]
                )

            return Result([])

    header("M9", "Evidence validator · deterministic gate")

    validator = EvidenceValidator(FakeGraph())

    supported = validator.validate(Claim("commit-001", "CHANGED", "dependency-001"))

    absent = EvidenceValidator(FakeGraph(exists=False)).validate(
        Claim("commit-001", "AFFECTS", "dependency-001")
    )

    temporal = EvidenceValidator(FakeGraph(temporal="invalid")).validate(
        Claim("commit-001", "CHANGED", "dependency-001")
    )

    conflict = EvidenceValidator(FakeGraph(contradiction=True)).validate(
        Claim("commit-001", "CHANGED", "dependency-001")
    )

    missing = EvidenceValidator(FakeGraph(evidence=False)).validate(
        Claim("commit-001", "CHANGED", "dependency-001")
    )

    expected_pipeline = (
        "graph_validation",
        "evidence_lookup",
        "temporal_check",
        "contradiction_check",
        "evidence_classification",
    )

    try:
        assert supported.classification == ClaimClassification.OBSERVED
        assert (
            supported.temporal_check is not None
            and supported.temporal_check.valid is True
        )

        assert absent.classification == ClaimClassification.UNKNOWN
        assert absent.pipeline == expected_pipeline

        assert temporal.classification == ClaimClassification.CONTRADICTED
        assert conflict.classification == ClaimClassification.CONTRADICTED
        assert missing.classification == ClaimClassification.UNKNOWN

        assert supported.pipeline == expected_pipeline

    except AssertionError as exc:
        failure(str(exc) or "M9 deterministic assertions failed")
        return 1

    checks(
        [
            CheckResult(
                "Claim model",
                "PASS · subject/relationship/object are explicit",
            ),
            CheckResult(
                "Graph validation",
                "PASS · absent relationship → UNKNOWN",
            ),
            CheckResult(
                "Evidence lookup",
                "PASS · M4 provenance boundary consumed",
            ),
            CheckResult(
                "Temporal validation",
                "PASS · impossible ordering → CONTRADICTED",
            ),
            CheckResult(
                "Contradiction check",
                "PASS · contradictory source → CONTRADICTED",
            ),
            CheckResult(
                "Insufficient evidence",
                "PASS · relationship without evidence → UNKNOWN",
            ),
            CheckResult(
                "Classification",
                "PASS · no boolean truth / no confidence score",
            ),
            CheckResult(
                "Deterministic boundary",
                "PASS · no LLM involved in classification",
            ),
        ]
    )

    success("M9")
    return 0


def run_falkordb() -> int:
    """Run M9 against the real seeded software graph."""

    header("M9", "Evidence validator · real FalkorDB gate")

    client = GraphClient()

    try:
        client.ping()
        WorldLoader(client).load(SOFTWARE_WORLD, reset=True)

        investigator = Investigator(client)

        supported = investigator.validate_claim(
            Claim(
                "commit-001",
                "CHANGED",
                "dependency-gateway-sdk",
            )
        )

        absent = investigator.validate_claim(
            Claim(
                "commit-001",
                "AFFECTS",
                "dependency-gateway-sdk",
            )
        )

        temporal = investigator.validate_claim(
            Claim(
                "config-001",
                "AFFECTS",
                "metric-001",
            )
        )

        missing = investigator.validate_claim(
            Claim(
                "infra-event-001",
                "AFFECTS",
                "metric-001",
            )
        )

        expected_pipeline = (
            "graph_validation",
            "evidence_lookup",
            "temporal_check",
            "contradiction_check",
            "evidence_classification",
        )

        assert supported.classification == ClaimClassification.OBSERVED
        assert supported.evidence_found
        assert (
            supported.temporal_check is not None
            and supported.temporal_check.valid is True
        )
        assert supported.pipeline == expected_pipeline

        assert absent.classification == ClaimClassification.UNKNOWN
        assert absent.pipeline == expected_pipeline

        assert temporal.classification == ClaimClassification.CONTRADICTED
        assert temporal.pipeline == expected_pipeline
        assert (
            temporal.temporal_check is not None
            and temporal.temporal_check.valid is False
        )

        assert missing.classification == ClaimClassification.UNKNOWN
        assert not missing.evidence_found
        assert missing.pipeline == expected_pipeline

    except (
        AssertionError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        failure(str(exc))
        return 1

    info("Supported claim", supported.classification)
    info("Absent relationship", absent.classification)
    info("Temporal trap", temporal.classification)
    info("Missing evidence", missing.classification)

    checks(
        [
            CheckResult(
                "FalkorDB connectivity",
                "PASS · real graph connection",
            ),
            CheckResult(
                "Supported relationship",
                "PASS · commit-001 CHANGED dependency-gateway-sdk → OBSERVED",
            ),
            CheckResult(
                "Absent relationship",
                "PASS · nonexistent directed edge → UNKNOWN",
            ),
            CheckResult(
                "Temporal contradiction",
                "PASS · config-001 after metric-001 → CONTRADICTED",
            ),
            CheckResult(
                "Missing evidence",
                "PASS · infra-event-001 relationship → UNKNOWN",
            ),
            CheckResult(
                "M9 pipeline",
                "PASS · graph → evidence → temporal → contradiction → classification",
            ),
        ]
    )

    success("M9")
    return 0


def run_ollama(model: str, max_steps: int) -> int:
    """
    Run the real M8 investigator and then pass a real LLM-proposed
    relationship through the deterministic M9 validator.

    The LLM supplies only:
        subject
        relationship
        object

    The LLM does not supply:
        classification
        evidence status
        confidence
        verdict

    M9 determines the classification independently.
    """

    header("M9", "Evidence validator · real Ollama integration")

    provider = OllamaProvider(model)
    client = GraphClient()

    try:
        # ------------------------------------------------------------------
        # 1. Real Ollama connectivity
        # ------------------------------------------------------------------
        provider.check()

        # ------------------------------------------------------------------
        # 2. Real FalkorDB graph
        # ------------------------------------------------------------------
        client.ping()
        WorldLoader(client).load(SOFTWARE_WORLD, reset=True)

        investigator = Investigator(client)

        # ------------------------------------------------------------------
        # 3. Real M8 investigation
        # ------------------------------------------------------------------
        state = investigator.start_investigation(
            "Why did incident-001 happen?",
            target_id="incident-001",
        )

        run = AgenticInvestigator(
            investigator,
            provider,
            max_steps=max_steps,
        ).run(state)

        if run.status not in {"DONE", "MAX_STEPS"}:
            raise AssertionError(f"unexpected agent status: {run.status}")

        if not any(step.status == "EXECUTED" for step in run.steps):
            raise AssertionError(
                "Ollama produced no executable investigation tool call"
            )

        # ------------------------------------------------------------------
        # 4. Real Ollama proposes a relationship claim.
        #
        # The model is explicitly prohibited from returning a verdict.
        # ------------------------------------------------------------------
        proposal_response = provider.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are the claim proposer for Continuum M9. "
                        "Use the investigation state to propose exactly one "
                        "graph relationship claim. "
                        "Call propose_claim exactly once. "
                        "The claim must contain only subject, relationship, "
                        "and object. "
                        "Do not provide a verdict, classification, confidence, "
                        "evidence status, or explanation."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Investigation state:\n"
                        f"{state_context(state)}\n\n"
                        "Propose one relationship claim from the investigated "
                        "graph. Continuum will independently validate the "
                        "claim."
                    ),
                },
            ],
            tools=[CLAIM_PROPOSAL_TOOL],
        )

        if len(proposal_response.tool_calls) != 1:
            raise AssertionError("expected exactly one propose_claim tool call")

        proposal = proposal_response.tool_calls[0]

        if proposal.name != "propose_claim":
            raise AssertionError(f"unexpected proposal tool: {proposal.name}")

        arguments = proposal.arguments

        if set(arguments) != {
            "subject",
            "relationship",
            "object",
        }:
            raise AssertionError(
                "LLM claim proposal contained fields outside "
                "subject/relationship/object"
            )

        if not all(
            isinstance(arguments[field], str) and arguments[field].strip()
            for field in ("subject", "relationship", "object")
        ):
            raise AssertionError(
                "LLM claim proposal contains empty or non-string fields"
            )

        claim = Claim(
            subject=arguments["subject"],
            relationship=arguments["relationship"],
            object=arguments["object"],
        )

        # ------------------------------------------------------------------
        # 5. M9 validates the model proposal.
        #
        # This is the architectural boundary:
        #
        #     LLM → proposes
        #     M9 → determines classification
        # ------------------------------------------------------------------
        validation = investigator.validate_claim(claim)

        expected_pipeline = (
            "graph_validation",
            "evidence_lookup",
            "temporal_check",
            "contradiction_check",
            "evidence_classification",
        )

        if validation.pipeline != expected_pipeline:
            raise AssertionError(f"unexpected M9 pipeline: {validation.pipeline}")

        if validation.classification not in ClaimClassification.ALL:
            raise AssertionError(
                f"invalid M9 classification: {validation.classification}"
            )

        # ------------------------------------------------------------------
        # 6. Controlled unsupported-claim rejection.
        #
        # This is deliberately independent of model behavior.
        # The relationship is absent from the seeded graph.
        # ------------------------------------------------------------------
        rejected = investigator.validate_claim(
            Claim(
                "commit-001",
                "AFFECTS",
                "dependency-gateway-sdk",
            )
        )

        if rejected.classification != ClaimClassification.UNKNOWN:
            raise AssertionError("M9 accepted an unsupported relationship")

        if rejected.message != "Insufficient evidence.":
            raise AssertionError(
                "unsupported claim did not produce explicit uncertainty"
            )

        if rejected.pipeline != expected_pipeline:
            raise AssertionError(
                f"unsupported claim used unexpected pipeline: {rejected.pipeline}"
            )

    except (
        AssertionError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        failure(str(exc))
        return 1

    info("Model", model)
    info("M8 agent status", run.status)
    info("M8 state version", str(state.version))
    info(
        "M8 executed operations",
        ", ".join(step.operation for step in state.history),
    )
    info(
        "LLM proposed claim",
        f"{claim.subject} -[{claim.relationship}]-> {claim.object}",
    )
    info("M9 classification", validation.classification)
    info("M9 evidence found", str(validation.evidence_found))
    info("Controlled invalid claim", rejected.classification)

    checks(
        [
            CheckResult(
                "Ollama connectivity",
                "PASS · real /api/tags check",
            ),
            CheckResult(
                "FalkorDB graph",
                "PASS · real software world loaded",
            ),
            CheckResult(
                "M8 investigation",
                "PASS · real model executed investigation tools",
            ),
            CheckResult(
                "LLM claim proposal",
                "PASS · real model called propose_claim",
            ),
            CheckResult(
                "M9 deterministic verdict",
                "PASS · EvidenceValidator computed classification",
            ),
            CheckResult(
                "M9 pipeline",
                "PASS · graph → evidence → temporal → contradiction → classification",
            ),
            CheckResult(
                "Unsupported claim rejection",
                "PASS · controlled invalid relationship → UNKNOWN",
            ),
            CheckResult(
                "Authority boundary",
                "PASS · model supplied no evidence classification",
            ),
        ]
    )

    success("M9")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify M9 evidence validator")

    parser.add_argument(
        "--mode",
        choices=("deterministic", "falkordb", "ollama"),
        default="deterministic",
    )

    parser.add_argument(
        "--model",
        default=os.getenv(
            "CONTINUUM_OLLAMA_MODEL",
            "qwen3:30b-a3b-instruct-2507-q4_K_M",
        ),
    )

    parser.add_argument(
        "--max-steps",
        type=int,
        default=10,
    )

    args = parser.parse_args()

    if args.max_steps < 1:
        parser.error("--max-steps must be >= 1")

    if args.mode == "deterministic":
        return run_deterministic()

    if args.mode == "falkordb":
        return run_falkordb()

    return run_ollama(args.model, args.max_steps)


if __name__ == "__main__":
    raise SystemExit(main())
