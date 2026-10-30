from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from continuum.core.models import EvidenceStatus, GraphRelationship, InvestigationPath
from continuum.graph.client import GraphClient
from continuum.graph.provenance import relationship_with_evidence
from continuum.temporal.model import TemporalCheck, check_temporal_sequence
from continuum.validation.model import Claim, ClaimClassification, ClaimValidation

_CYPHER_TOKEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EvidenceValidator:
    """Deterministic M9 evidence validator.

    The validator is deliberately independent of the LLM. A caller may supply
    a claim proposed by an LLM, but only this layer can assign its evidentiary
    classification.
    """

    def __init__(
        self,
        graph: GraphClient,
        conflict_checker: Callable[[list[InvestigationPath]], list[str]] | None = None,
    ):
        self.graph = graph
        self._conflict_checker = conflict_checker

    def validate(self, claim: Claim) -> ClaimValidation:
        """Run graph, evidence, temporal, contradiction, then classification."""
        if not isinstance(claim, Claim):
            raise TypeError("claim must be a Claim")
        self._validate_relationship_token(claim.relationship)

        relationships = self._validate_graph_relationship(claim)
        pipeline = ["graph_validation"]

        if not relationships:
            pipeline.extend(
                (
                    "evidence_lookup",
                    "temporal_check",
                    "contradiction_check",
                    "evidence_classification",
                )
            )
            return ClaimValidation(
                claim=claim,
                classification=ClaimClassification.UNKNOWN,
                graph_relationships=(),
                evidence=(),
                temporal_check=None,
                contradictions=(),
                graph_valid=False,
                evidence_found=False,
                pipeline=tuple(pipeline),
                reason="Claimed relationship does not exist in the graph.",
            )

        evidence, resolved = self._lookup_evidence(relationships)
        pipeline.append("evidence_lookup")

        temporal_check = self._check_temporal(claim, resolved)
        pipeline.append("temporal_check")

        contradictions = self._check_contradictions(
            claim, resolved, evidence, temporal_check, self._conflict_checker
        )
        pipeline.append("contradiction_check")

        classification, reason = self._classify(
            relationships,
            evidence,
            temporal_check,
            contradictions,
        )
        pipeline.append("evidence_classification")

        return ClaimValidation(
            claim=claim,
            classification=classification,
            graph_relationships=tuple(resolved),
            evidence=tuple(evidence),
            temporal_check=temporal_check,
            contradictions=tuple(contradictions),
            graph_valid=True,
            evidence_found=bool(evidence),
            pipeline=tuple(pipeline),
            reason=reason,
        )

    def validate_relationship(
        self,
        subject: str,
        relationship: str,
        object: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ClaimValidation:
        """Convenience boundary for callers that already have relationship fields."""
        return self.validate(
            Claim(
                subject=subject,
                relationship=relationship,
                object=object,
                metadata=dict(metadata or {}),
            )
        )

    def _validate_graph_relationship(self, claim: Claim) -> list[GraphRelationship]:
        result = self.graph.read(
            f"""
            MATCH (source {{id:$subject}})-[r:{claim.relationship}]->(target {{id:$object}})
            RETURN
                source.id,
                type(r),
                target.id,
                r.edge_id,
                r.timestamp,
                r.valid_from,
                r.valid_until,
                coalesce(r.evidence_status, 'UNKNOWN')
            ORDER BY r.edge_id
            """,
            {"subject": claim.subject, "object": claim.object},
        )

        relationships: list[GraphRelationship] = []
        for row in result.result_set:
            (
                source_id,
                relation,
                target_id,
                edge_id,
                timestamp,
                valid_from,
                valid_until,
                status,
            ) = row
            relationships.append(
                GraphRelationship(
                    source_id=str(source_id),
                    relationship=str(relation),
                    target_id=str(target_id),
                    edge_id=str(edge_id) if edge_id is not None else None,
                    timestamp=timestamp,
                    valid_from=valid_from,
                    valid_until=valid_until,
                    evidence_status=str(status),
                )
            )
        return relationships

    def _lookup_evidence(
        self, relationships: list[GraphRelationship]
    ) -> tuple[list[Any], list[GraphRelationship]]:
        evidence = []
        resolved: list[GraphRelationship] = []
        for relationship in relationships:
            matches = relationship_with_evidence(
                self.graph,
                relationship.source_id,
                relationship.target_id,
                edge_id=relationship.edge_id,
            )
            # relationship_with_evidence is the existing M4 provenance boundary.
            for match in matches:
                if (
                    match.source_id == relationship.source_id
                    and match.target_id == relationship.target_id
                    and match.relationship == relationship.relationship
                    and match.edge_id == relationship.edge_id
                ):
                    resolved.append(match)
                    evidence.extend(match.evidence)
        unique_evidence = {item.id: item for item in evidence}
        return list(unique_evidence.values()), resolved

    def _check_temporal(
        self,
        claim: Claim,
        relationships: list[GraphRelationship],
    ) -> TemporalCheck:
        """Apply the existing M5 temporal sequence check to the claim edge."""
        node_rows = self.graph.read(
            """
            MATCH (subject {id:$subject}), (object {id:$object})
            RETURN
                subject.id,
                properties(subject),
                object.id,
                properties(object)
            """,
            {"subject": claim.subject, "object": claim.object},
        ).result_set
        if not node_rows:
            return TemporalCheck(None, "claim endpoints are missing from the graph")

        row = node_rows[0]
        subject_id, subject_properties, object_id, object_properties = row
        node_ids = (str(subject_id), str(object_id))
        node_records = (
            dict(subject_properties or {}),
            dict(object_properties or {}),
        )
        edge_records = [
            {
                "edge_id": relationship.edge_id,
                "timestamp": relationship.timestamp,
                "valid_from": relationship.valid_from,
                "valid_until": relationship.valid_until,
            }
            for relationship in relationships
        ]

        # A single claimed relationship may have multiple persisted edges. A
        # claim is temporally admissible only when every matching edge is valid.
        checks = [
            check_temporal_sequence(node_ids, node_records, [edge_record])
            for edge_record in edge_records
        ]
        invalid = next((check for check in checks if check.valid is False), None)
        if invalid is not None:
            return invalid
        if any(check.valid is True for check in checks):
            if all(check.valid is True for check in checks):
                return TemporalCheck(True, "claim temporally consistent")
            return TemporalCheck(
                None, "some matching relationships lack temporal metadata"
            )
        return TemporalCheck(None, "missing temporal metadata")

    @staticmethod
    def _check_contradictions(
        claim: Claim,
        relationships: list[GraphRelationship],
        evidence: list[Any],
        temporal_check: TemporalCheck,
        conflict_checker: Callable[[list[InvestigationPath]], list[str]] | None,
    ) -> list[str]:
        contradictions: list[str] = []

        # Reuse the M6 conflict primitive when the validator is reached through
        # Investigator.validate_claim(). The one-hop path is the validator's
        # deterministic representation of this relationship claim.
        if conflict_checker is not None:
            path = InvestigationPath(
                node_ids=(claim.subject, claim.object),
                relationships=(claim.relationship,),
                edge_ids=(relationships[0].edge_id if relationships else None,),
                temporal_status=temporal_check.status,
                temporal_reason=temporal_check.reason,
                evidence=tuple(evidence),
            )
            contradictions.extend(conflict_checker([path]))

        if temporal_check.valid is False:
            contradictions.append(
                f"Claim {claim.subject} -[{claim.relationship}]-> {claim.object} rejected: "
                f"{temporal_check.reason}"
            )

        for relationship in relationships:
            if relationship.evidence_status == EvidenceStatus.CONTRADICTED:
                contradictions.append(
                    f"Graph relationship {relationship.edge_id or relationship.relationship} "
                    "is marked CONTRADICTED"
                )

        for item in evidence:
            if item.status == EvidenceStatus.CONTRADICTED:
                contradictions.append(
                    f"Evidence {item.id} contradicts claim "
                    f"{claim.subject} -[{claim.relationship}]-> {claim.object}"
                )

        return list(dict.fromkeys(contradictions))

    @staticmethod
    def _classify(
        relationships: list[GraphRelationship],
        evidence: list[Any],
        temporal_check: TemporalCheck,
        contradictions: list[str],
    ) -> tuple[str, str]:
        if contradictions or temporal_check.valid is False:
            return ClaimClassification.CONTRADICTED, contradictions[0]

        if not evidence:
            return (
                ClaimClassification.UNKNOWN,
                "Relationship exists, but supporting evidence is missing.",
            )

        if temporal_check.valid is None:
            return (
                ClaimClassification.UNKNOWN,
                "Supporting evidence exists, but temporal validity is unknown.",
            )

        statuses = {item.status for item in evidence}
        relationship_statuses = {item.evidence_status for item in relationships}

        if EvidenceStatus.CONTRADICTED in statuses | relationship_statuses:
            return (
                ClaimClassification.CONTRADICTED,
                "Contradictory evidence is attached to the claim.",
            )
        if EvidenceStatus.SUPPORTED_INFERENCE in statuses | relationship_statuses:
            return (
                ClaimClassification.SUPPORTED_INFERENCE,
                "Graph relationship and supporting evidence validate the inference.",
            )
        if EvidenceStatus.DERIVED in statuses | relationship_statuses:
            return (
                ClaimClassification.DERIVED,
                "Graph relationship and evidence support a derived relationship.",
            )
        if statuses <= {EvidenceStatus.OBSERVED}:
            return (
                ClaimClassification.OBSERVED,
                "Graph relationship is directly supported by observed source evidence.",
            )
        return (
            ClaimClassification.UNKNOWN,
            "Evidence status is insufficient to establish the claim.",
        )

    @staticmethod
    def _validate_relationship_token(relationship: str) -> None:
        if not _CYPHER_TOKEN.fullmatch(relationship):
            raise ValueError(f"Invalid graph relationship: {relationship}")
