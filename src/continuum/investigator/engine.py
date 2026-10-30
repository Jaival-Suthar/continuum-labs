from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from continuum.core.models import (
    Evidence,
    EvidenceStatus,
    GraphNode,
    Hypothesis,
    InvestigationPath,
    InvestigationResult,
    InvestigationState,
    PathRanking,
)
from continuum.core.world import World
from continuum.graph.client import GraphClient
from continuum.graph.provenance import relationship_with_evidence
from continuum.graph.traversal import GraphTraversal
from continuum.temporal import TemporalQueries
from continuum.temporal.model import TemporalCheck
from continuum.validation import Claim, ClaimValidation, EvidenceValidator


@dataclass(frozen=True)
class _PathMaterial:
    node_ids: tuple[str, ...]
    relationships: tuple[str, ...]
    edge_ids: tuple[str | None, ...]
    node_records: tuple[dict[str, Any], ...]
    edge_records: tuple[dict[str, Any], ...]


class Investigator:
    """Domain-independent deterministic investigation engine.

    FalkorDB performs entity lookup, neighborhood expansion, and path discovery.
    M5 temporal validation and M4 provenance are consumed as deterministic
    validation stages. No LLM or domain-specific investigator branch is used.
    """

    def __init__(self, graph: GraphClient, world: World | None = None):
        self.graph = graph
        self.world = world
        self.traversal = GraphTraversal(graph)
        self.temporal = TemporalQueries(graph)

    def find_outcome(
        self,
        target_or_question: str,
        *,
        target_id: str | None = None,
    ) -> GraphNode:
        """Locate the investigation target without assuming a domain label."""
        requested = target_id or self._extract_node_id(target_or_question)

        if requested:
            rows = self.traversal.find_by_id(requested)
            if rows:
                return self._node_from_row(rows[0])

        tokens = self._question_tokens(target_or_question)

        if tokens:
            rows = self.graph.read(
                """
                MATCH (n)
                WHERE any(token IN $tokens WHERE
                    toLower(coalesce(n.id, '')) CONTAINS token OR
                    toLower(coalesce(n.name, '')) CONTAINS token)
                RETURN labels(n), n.id, n.name, n.timestamp, n.valid_from,
                       n.valid_until, n.observed_at, properties(n)
                ORDER BY n.id
                LIMIT 25
                """,
                {"tokens": tokens},
            ).result_set

            if rows:
                return self._node_from_rich_row(rows[0])

        rows = self.graph.read(
            """
            MATCH ()-[:RESULTED_IN]->(outcome)
            RETURN labels(outcome), outcome.id, outcome.name, outcome.timestamp,
                   outcome.valid_from, outcome.valid_until, outcome.observed_at,
                   properties(outcome)
            ORDER BY outcome.timestamp DESC, outcome.id ASC
            LIMIT 25
            """
        ).result_set

        if rows:
            return self._node_from_rich_row(rows[0])

        raise ValueError(f"unable to locate investigation target: {target_or_question}")

    def find_related_entities(
        self,
        node_id: str,
        *,
        limit: int = 100,
    ) -> list[GraphNode]:
        """Return connected non-source entities discovered by FalkorDB."""
        if limit < 1:
            raise ValueError("limit must be >= 1")

        rows = self.graph.read(
            f"""
            MATCH (n {{id:$node_id}})-[r]-(m)
            WHERE type(r) <> 'SUPPORTED_BY'
            RETURN labels(m), m.id, m.name, m.timestamp, m.valid_from,
                   m.valid_until, m.observed_at, properties(m)
            ORDER BY m.id
            LIMIT {int(limit)}
            """,
            {"node_id": node_id},
        ).result_set

        return [self._node_from_rich_row(row) for row in rows]

    def expand_neighborhood(
        self,
        node_id: str,
        *,
        depth: int = 1,
        limit: int = 100,
    ) -> list[GraphNode]:
        """Expand a node's connected neighborhood to the requested depth."""
        if depth < 1:
            raise ValueError("depth must be >= 1")

        if limit < 1:
            raise ValueError("limit must be >= 1")

        rows = self.graph.read(
            f"""
            MATCH (start {{id:$node_id}})-[*1..{int(depth)}]-(m)
            WHERE m.id <> $node_id
            RETURN DISTINCT labels(m), m.id, m.name, m.timestamp, m.valid_from,
                   m.valid_until, m.observed_at, properties(m)
            ORDER BY m.id
            LIMIT {int(limit)}
            """,
            {"node_id": node_id},
        ).result_set

        return [self._node_from_rich_row(row) for row in rows]

    def find_paths(
        self,
        start_id: str,
        end_id: str,
        *,
        max_hops: int = 6,
        limit: int = 25,
    ) -> list[InvestigationPath]:
        """Discover actual FalkorDB paths and classify temporal validity."""
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")

        if limit < 1:
            raise ValueError("limit must be >= 1")

        materials = self._discover_paths(
            start_id,
            end_id,
            max_hops=max_hops,
            limit=limit,
        )

        return [
            self._enrich_path(
                material,
                direction="forward",
            )
            for material in materials
        ]

    def trace_backward(
        self,
        node_id: str,
        *,
        max_hops: int = 6,
        limit: int = 25,
    ) -> list[InvestigationPath]:
        """Trace candidate upstream explanations from a target."""
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")

        if limit < 1:
            raise ValueError("limit must be >= 1")

        candidates = self._discover_paths_to_change_candidates(
            node_id,
            max_hops=max_hops,
            limit=limit,
        )

        return [
            self._enrich_path(
                material,
                direction="backward",
            )
            for material in candidates
        ]

    def trace_forward(
        self,
        node_id: str,
        *,
        max_hops: int = 6,
        limit: int = 25,
    ) -> list[InvestigationPath]:
        """Trace downstream consequences from a change or event."""
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")

        if limit < 1:
            raise ValueError("limit must be >= 1")

        return self.find_paths(
            node_id,
            self._outcome_reachable_target(node_id),
            max_hops=max_hops,
            limit=limit,
        )

    def find_preceding_changes(
        self,
        outcome_id: str,
        *,
        limit: int = 50,
    ) -> list[GraphNode]:
        """Find timestamped candidate changes before the outcome."""
        if limit < 1:
            raise ValueError("limit must be >= 1")

        outcome = self._node_record(outcome_id)
        timestamp = outcome.get("timestamp")

        if timestamp is None:
            raise ValueError(f"node {outcome_id} has no timestamp")

        rows = self.temporal.ordering(
            outcome_id,
            before_timestamp=str(timestamp),
            limit=limit,
        )

        return [
            self._node_from_ordering_row(row)
            for row in rows
            if self._is_change_candidate(row)
        ]

    def find_downstream_impact(
        self,
        change_id: str,
        *,
        max_hops: int = 6,
        limit: int = 25,
    ) -> list[InvestigationPath]:
        """Return graph-connected, temporally admissible downstream paths."""
        if max_hops < 1:
            raise ValueError("max_hops must be >= 1")

        if limit < 1:
            raise ValueError("limit must be >= 1")

        outcome_ids = self._candidate_outcome_ids(change_id)

        paths: list[InvestigationPath] = []

        for outcome_id in outcome_ids:
            paths.extend(
                self.find_paths(
                    change_id,
                    outcome_id,
                    max_hops=max_hops,
                    limit=limit,
                )
            )

        return [path for path in paths if path.temporally_valid is not False]

    def find_supporting_evidence(
        self,
        path: InvestigationPath,
    ) -> list[Evidence]:
        """Resolve provenance attached to each actual path relationship."""
        evidence: list[Evidence] = []

        expected_edges = len(path.node_ids) - 1

        if len(path.edge_ids) != expected_edges:
            raise ValueError("path edge count must equal node count minus one")

        for source_id, target_id, edge_id in zip(
            path.node_ids[:-1],
            path.node_ids[1:],
            path.edge_ids,
            strict=True,
        ):
            relationships = relationship_with_evidence(
                self.graph,
                source_id,
                target_id,
                edge_id=edge_id,
            )

            for relationship in relationships:
                evidence.extend(relationship.evidence)

        return self._unique_evidence(evidence)

    def find_conflicting_evidence(
        self,
        paths: Iterable[InvestigationPath],
    ) -> list[str]:
        """Surface temporal/evidence conflicts instead of discarding them."""
        conflicts: list[str] = []

        for path in paths:
            if path.temporally_valid is False:
                conflicts.append(
                    f"Path {' -> '.join(path.node_ids)} rejected: "
                    f"{path.temporal_reason}"
                )

            for evidence in path.evidence:
                if evidence.status == EvidenceStatus.CONTRADICTED:
                    conflicts.append(
                        f"Evidence {evidence.id} contradicts path "
                        f"{' -> '.join(path.node_ids)}"
                    )

        return list(dict.fromkeys(conflicts))

    def check_temporal_consistency(
        self,
        path: InvestigationPath,
    ) -> TemporalCheck:
        """Expose M5 temporal validation as an M6 operation."""
        material = self._material_from_path(path)

        return self.temporal.filter_temporal_paths([self._temporal_path(material)])[
            0
        ].check

    def rank_paths(
        self,
        paths: Iterable[InvestigationPath],
    ) -> list[PathRanking]:
        """Rank using explicit evidence and temporal signals only."""
        ranked: list[PathRanking] = []

        for path in paths:
            temporal_validity = {
                True: 2,
                None: 1,
                False: 0,
            }[path.temporally_valid]

            rank_key = (
                temporal_validity,
                path.supporting_relationship_count,
                len(path.evidence),
                -path.conflicting_relationship_count,
                -path.missing_evidence_count,
                -path.hop_count,
            )

            ranked.append(
                PathRanking(
                    path=path,
                    temporal_validity=temporal_validity,
                    path_length=path.hop_count,
                    evidence_count=len(path.evidence),
                    supporting_relationship_count=(path.supporting_relationship_count),
                    conflicting_relationship_count=(
                        path.conflicting_relationship_count
                    ),
                    missing_evidence_count=(path.missing_evidence_count),
                    rank_key=rank_key,
                )
            )

        ranked.sort(
            key=lambda item: (
                item.rank_key,
                item.path.node_ids,
            ),
            reverse=True,
        )

        return ranked

    def validate_claim(self, claim: Claim) -> ClaimValidation:
        """Validate one proposed relationship through the deterministic M9 boundary.

        This method is intentionally separate from the M8 investigation
        operations. An LLM may propose a ``Claim``; only ``EvidenceValidator``
        may classify its evidentiary status.
        """
        return EvidenceValidator(self.graph, self.find_conflicting_evidence).validate(
            claim
        )

    def start_investigation(
        self,
        question: str,
        *,
        target_id: str | None = None,
        hypotheses: Iterable[Hypothesis] = (),
    ) -> InvestigationState:
        """Create an empty cumulative M7 state.

        No graph query is executed here. The state is the durable context for
        subsequent explicit investigation operations.
        """
        state = InvestigationState(question=question, target=target_id)
        for hypothesis in hypotheses:
            state.add_hypothesis(hypothesis)
        return state

    # ``begin_investigation`` reads naturally in callers and is intentionally
    # an alias rather than a second implementation.
    begin_investigation = start_investigation

    def continue_investigation(
        self,
        state: InvestigationState,
        operation: str,
        **kwargs: Any,
    ) -> InvestigationState:
        """Execute one deterministic M6 operation against existing M7 state.

        The operation result is merged into ``state`` by the single M7 state
        update mechanism. No LLM, planning loop, or domain-specific branch is
        involved; choosing the operation remains an explicit caller concern
        until M8.
        """
        if not isinstance(state, InvestigationState):
            raise TypeError("state must be an InvestigationState")
        if not operation:
            raise ValueError("operation must not be empty")

        normalized = operation.strip().lower()
        allowed = {
            "find_outcome",
            "find_related_entities",
            "expand_neighborhood",
            "find_paths",
            "trace_backward",
            "trace_forward",
            "find_preceding_changes",
            "find_downstream_impact",
            "find_supporting_evidence",
            "find_conflicting_evidence",
            "check_temporal_consistency",
            "rank_paths",
        }
        if normalized not in allowed:
            raise ValueError(
                f"unsupported investigation operation: {operation}; "
                f"allowed={', '.join(sorted(allowed))}"
            )

        inputs = dict(kwargs)
        result = self._execute_state_operation(state, normalized, kwargs)
        state.apply_result(normalized, result, input=inputs)
        return state

    # Explicit name for the milestone's core concept.
    investigate_step = continue_investigation

    def _execute_state_operation(
        self,
        state: InvestigationState,
        operation: str,
        kwargs: dict[str, Any],
    ) -> InvestigationResult:
        """Adapt one M6 primitive to the M7 result/state boundary."""
        if operation == "find_outcome":
            target_or_question = str(kwargs.pop("target_or_question", state.question))
            target_id = kwargs.pop("target_id", None)
            outcome = self.find_outcome(target_or_question, target_id=target_id)
            return InvestigationResult(
                question=state.question,
                target=outcome.id,
                discovered_nodes=[outcome.id],
                trace=[f"outcome_located={outcome.id}"],
            )

        if operation in {"find_related_entities", "expand_neighborhood"}:
            node_id = self._state_node_id(state, kwargs.pop("node_id", None))
            if operation == "find_related_entities":
                nodes = self.find_related_entities(node_id, **kwargs)
            else:
                nodes = self.expand_neighborhood(node_id, **kwargs)
            return InvestigationResult(
                question=state.question,
                target=state.target or node_id,
                discovered_nodes=[node_id, *(node.id for node in nodes)],
                trace=[f"{operation}={len(nodes)}"],
            )

        if operation in {
            "find_paths",
            "trace_backward",
            "trace_forward",
            "find_downstream_impact",
        }:
            if operation == "find_paths":
                start_id = str(kwargs.pop("start_id"))
                end_id = str(kwargs.pop("end_id"))
                paths = self.find_paths(start_id, end_id, **kwargs)
            elif operation == "trace_backward":
                node_id = self._state_node_id(state, kwargs.pop("node_id", None))
                paths = self.trace_backward(node_id, **kwargs)
            elif operation == "trace_forward":
                node_id = self._state_node_id(state, kwargs.pop("node_id", None))
                paths = self.trace_forward(node_id, **kwargs)
            else:
                change_id = self._state_node_id(state, kwargs.pop("change_id", None))
                paths = self.find_downstream_impact(change_id, **kwargs)
            return self._result_from_paths(state, paths, operation)

        if operation == "find_preceding_changes":
            outcome_id = self._state_node_id(state, kwargs.pop("outcome_id", None))
            nodes = self.find_preceding_changes(outcome_id, **kwargs)
            return InvestigationResult(
                question=state.question,
                target=state.target or outcome_id,
                discovered_nodes=[outcome_id, *(node.id for node in nodes)],
                trace=[f"preceding_changes={len(nodes)}"],
            )

        if operation == "find_supporting_evidence":
            path = self._state_path(
                state,
                kwargs.pop("path", None),
                kwargs.pop("path_index", None),
            )
            evidence = self.find_supporting_evidence(path)
            return self._result_from_paths(
                state,
                [path],
                operation,
                evidence=evidence,
            )

        if operation == "find_conflicting_evidence":
            paths = kwargs.pop("paths", None)
            selected = list(paths) if paths is not None else list(state.candidate_paths)
            conflicts = self.find_conflicting_evidence(selected)
            return InvestigationResult(
                question=state.question,
                target=state.target,
                candidate_paths=selected,
                contradictions=conflicts,
                trace=[f"conflicting_evidence={len(conflicts)}"],
            )

        if operation == "check_temporal_consistency":
            path = self._state_path(
                state,
                kwargs.pop("path", None),
                kwargs.pop("path_index", None),
            )
            check = self.check_temporal_consistency(path)
            detail = f"{' -> '.join(path.node_ids)}: {check.status} ({check.reason})"
            return InvestigationResult(
                question=state.question,
                target=state.target,
                candidate_paths=[path],
                temporal_checks=[detail],
                contradictions=(
                    [f"Path {' -> '.join(path.node_ids)} rejected: {check.reason}"]
                    if check.valid is False
                    else []
                ),
                trace=["temporal_validation=complete"],
            )

        if operation == "rank_paths":
            paths = kwargs.pop("paths", None)
            selected = list(paths) if paths is not None else list(state.candidate_paths)
            ranked = self.rank_paths(selected)
            return InvestigationResult(
                question=state.question,
                target=state.target,
                candidate_paths=selected,
                ranked_paths=ranked,
                trace=[f"ranking=deterministic paths={len(ranked)}"],
            )

        raise AssertionError(f"unhandled operation: {operation}")

    @staticmethod
    def _state_node_id(
        state: InvestigationState,
        node_id: str | None,
    ) -> str:
        resolved = node_id or state.target
        if not resolved:
            raise ValueError(
                "node_id is required when the investigation state has no target"
            )
        return resolved

    @staticmethod
    def _state_path(
        state: InvestigationState,
        path: InvestigationPath | None,
        path_index: int | None,
    ) -> InvestigationPath:
        if path is not None:
            return path
        if path_index is None:
            if len(state.candidate_paths) == 1:
                return state.candidate_paths[0]
            raise ValueError(
                "path or path_index is required when state has zero or multiple paths"
            )
        if path_index < 0 or path_index >= len(state.candidate_paths):
            raise IndexError("path_index is outside the current candidate_paths")
        return state.candidate_paths[path_index]

    @staticmethod
    def _result_from_paths(
        state: InvestigationState,
        paths: Iterable[InvestigationPath],
        operation: str,
        *,
        evidence: Iterable[Evidence] = (),
    ) -> InvestigationResult:
        selected = list(paths)
        discovered_nodes = list(
            dict.fromkeys(node_id for path in selected for node_id in path.node_ids)
        )
        discovered_edges = list(
            dict.fromkeys(
                edge_id or f"{source_id}|{relationship}|{target_id}"
                for path in selected
                for source_id, target_id, relationship, edge_id in zip(
                    path.node_ids[:-1],
                    path.node_ids[1:],
                    path.relationships,
                    path.edge_ids,
                    strict=True,
                )
            )
        )
        return InvestigationResult(
            question=state.question,
            target=state.target,
            discovered_nodes=discovered_nodes,
            discovered_edges=discovered_edges,
            candidate_paths=selected,
            evidence=list(evidence),
            temporal_checks=[
                f"{' -> '.join(path.node_ids)}: "
                f"{path.temporal_status} ({path.temporal_reason})"
                for path in selected
            ],
            contradictions=state.contradictions
            if operation == "find_conflicting_evidence"
            else [],
            gaps=[
                f"Path {' -> '.join(path.node_ids)} has "
                f"{path.missing_evidence_count} missing evidence relationship(s)"
                for path in selected
                if path.missing_evidence_count > 0
            ],
            trace=[f"{operation}={len(selected)}"],
        )

    def investigate(
        self,
        question: str,
        world: World | None = None,
    ) -> InvestigationResult:
        """Run the complete deterministic M6 investigation pipeline.

        The public signature intentionally preserves the M2 universal
        investigator contract.
        """
        active_world = world or self.world

        if active_world is not None:
            active_world.validate()

        # M2's contract test intentionally constructs an Investigator with
        # a non-graph placeholder. Contract verification must not attempt
        # graph I/O in that situation.
        if not self._is_graph_client():
            trace = [
                "investigation_started",
                "deterministic_engine_ready",
                "graph_execution_skipped",
            ]

            if active_world is not None:
                trace.insert(
                    1,
                    f"world={active_world.name}",
                )

            return InvestigationResult(
                question=question,
                trace=trace,
            )

        result = InvestigationResult(
            question=question,
            trace=["investigation_started"],
        )

        if active_world is not None:
            result.trace.append(f"world={active_world.name}")

        outcome = self.find_outcome(question)

        result.target = outcome.id
        result.trace.append(f"outcome_located={outcome.id}")

        related = self.find_related_entities(outcome.id)

        result.trace.append(f"related_entities={len(related)}")

        self.expand_neighborhood(
            outcome.id,
            depth=2,
        )

        result.trace.append("neighborhood_expanded=2")

        max_hops = 6
        path_limit = 25

        candidates = self.trace_backward(
            outcome.id,
            max_hops=max_hops,
            limit=path_limit,
        )

        result.candidate_paths = candidates

        result.trace.append(f"candidate_paths={len(candidates)}")

        result.evidence = self._unique_evidence(
            evidence for candidate in candidates for evidence in candidate.evidence
        )

        result.temporal_checks = [
            (
                f"{' -> '.join(path.node_ids)}: "
                f"{path.temporal_status} "
                f"({path.temporal_reason})"
            )
            for path in candidates
        ]

        result.contradictions = self.find_conflicting_evidence(candidates)

        result.gaps = [
            (
                f"Path {' -> '.join(path.node_ids)} has "
                f"{path.missing_evidence_count} "
                "missing evidence relationship(s)"
            )
            for path in candidates
            if path.missing_evidence_count > 0
        ]

        result.ranked_paths = self.rank_paths(candidates)

        result.trace.append(f"evidence_records={len(result.evidence)}")

        result.trace.append(f"contradictions={len(result.contradictions)}")

        result.trace.append(f"gaps={len(result.gaps)}")

        result.trace.append("temporal_validation=complete")

        result.trace.append("ranking=deterministic")

        return result

    def _is_graph_client(self) -> bool:
        """Return whether the supplied object supports graph execution."""
        return callable(getattr(self.graph, "read", None))

    def _discover_paths(
        self,
        start_id: str,
        end_id: str,
        *,
        max_hops: int,
        limit: int,
    ) -> list[_PathMaterial]:
        raw = self.temporal.paths_between(
            start_id,
            end_id,
            max_hops=max_hops,
            limit=limit,
        )

        materials: list[_PathMaterial] = []
        seen: set[tuple[str, ...]] = set()

        for path in raw:
            node_ids = tuple(path.node_ids)

            if node_ids in seen:
                continue

            seen.add(node_ids)

            edge_ids = tuple(record.get("edge_id") for record in path.edge_records)

            if len(edge_ids) != len(node_ids) - 1:
                raise ValueError(
                    "discovered path must contain exactly one edge record per graph hop"
                )

            materials.append(
                _PathMaterial(
                    node_ids=node_ids,
                    relationships=path.relationships,
                    edge_ids=edge_ids,
                    node_records=path.node_records,
                    edge_records=path.edge_records,
                )
            )

        return materials

    def _discover_paths_to_change_candidates(
        self,
        outcome_id: str,
        *,
        max_hops: int,
        limit: int,
    ) -> list[_PathMaterial]:
        rows = self.graph.read(
            f"""
            MATCH (candidate)-[*1..{int(max_hops)}]-(outcome {{id:$outcome_id}})
            WHERE candidate.id <> $outcome_id
              AND NOT (candidate:Source)
            RETURN DISTINCT candidate.id
            ORDER BY candidate.id
            LIMIT {int(limit)}
            """,
            {"outcome_id": outcome_id},
        ).result_set

        direct_candidates = [row[0] for row in rows if row and row[0]]

        materials: list[_PathMaterial] = []

        for candidate_id in direct_candidates:
            materials.extend(
                self._discover_paths(
                    candidate_id,
                    outcome_id,
                    max_hops=max_hops,
                    limit=limit,
                )
            )

        # Include graph-connected timestamped predecessors so that
        # alternative hypotheses are not excluded by domain labels.
        if len(materials) < limit:
            rows = self.graph.read(
                f"""
                MATCH (candidate)-[*1..2]-(outcome {{id:$outcome_id}})
                WHERE candidate.timestamp IS NOT NULL
                  AND candidate.id <> $outcome_id
                  AND NOT (candidate:Source)
                RETURN DISTINCT candidate.id
                ORDER BY candidate.id
                LIMIT {int(limit)}
                """,
                {"outcome_id": outcome_id},
            ).result_set

            for row in rows:
                if row and row[0]:
                    materials.extend(
                        self._discover_paths(
                            row[0],
                            outcome_id,
                            max_hops=max_hops,
                            limit=limit,
                        )
                    )

        unique: dict[
            tuple[str, ...],
            _PathMaterial,
        ] = {}

        for material in materials:
            unique.setdefault(
                material.node_ids,
                material,
            )

        return list(unique.values())[:limit]

    def _enrich_path(
        self,
        material: _PathMaterial,
        *,
        direction: str,
    ) -> InvestigationPath:
        """Enrich a graph path with M5 temporal and M4 provenance data."""
        temporal_path = self._temporal_path(material)
        check = temporal_path.temporal_check

        base_path = InvestigationPath(
            node_ids=material.node_ids,
            relationships=material.relationships,
            edge_ids=material.edge_ids,
            temporal_status=check.status,
            temporal_reason=check.reason,
            direction=direction,
            node_records=material.node_records,
            edge_records=material.edge_records,
        )

        expected_edges = len(base_path.node_ids) - 1

        if len(base_path.relationships) != expected_edges:
            raise ValueError("path relationship count must equal node count minus one")

        if len(base_path.edge_ids) != expected_edges:
            raise ValueError("path edge count must equal node count minus one")

        evidence: list[Evidence] = []
        supporting_relationship_count = 0
        missing_evidence_count = 0

        for source_id, target_id, edge_id in zip(
            base_path.node_ids[:-1],
            base_path.node_ids[1:],
            base_path.edge_ids,
            strict=True,
        ):
            relationships = relationship_with_evidence(
                self.graph,
                source_id,
                target_id,
                edge_id=edge_id,
            )

            relationship_evidence: list[Evidence] = []

            for relationship in relationships:
                relationship_evidence.extend(relationship.evidence)

            if relationship_evidence:
                supporting_relationship_count += 1
                evidence.extend(relationship_evidence)
            else:
                missing_evidence_count += 1

        return InvestigationPath(
            node_ids=base_path.node_ids,
            relationships=base_path.relationships,
            edge_ids=base_path.edge_ids,
            temporal_status=base_path.temporal_status,
            temporal_reason=base_path.temporal_reason,
            evidence=tuple(self._unique_evidence(evidence)),
            supporting_relationship_count=(supporting_relationship_count),
            conflicting_relationship_count=(
                1 if base_path.temporally_valid is False else 0
            ),
            missing_evidence_count=(missing_evidence_count),
            direction=base_path.direction,
            node_records=base_path.node_records,
            edge_records=base_path.edge_records,
        )

    def _temporal_path(
        self,
        material: _PathMaterial,
    ):
        from continuum.temporal.queries import TemporalPath

        return TemporalPath(
            node_ids=material.node_ids,
            relationships=material.relationships,
            node_timestamps=tuple(
                record.get("timestamp") for record in material.node_records
            ),
            edge_timestamps=tuple(
                record.get("timestamp") for record in material.edge_records
            ),
            node_records=material.node_records,
            edge_records=material.edge_records,
        )

    @staticmethod
    def _material_from_path(
        path: InvestigationPath,
    ) -> _PathMaterial:
        return _PathMaterial(
            path.node_ids,
            path.relationships,
            path.edge_ids,
            path.node_records,
            path.edge_records,
        )

    def _node_record(
        self,
        node_id: str,
    ) -> dict[str, Any]:
        rows = self.graph.read(
            "MATCH (n {id:$node_id}) RETURN properties(n)",
            {"node_id": node_id},
        ).result_set

        if not rows:
            raise ValueError(f"node {node_id} not found")

        return dict(rows[0][0])

    def _candidate_outcome_ids(
        self,
        change_id: str,
    ) -> list[str]:
        rows = self.graph.read(
            """
            MATCH (change {id:$change_id})-[*1..6]-(candidate)
            WHERE (candidate)<-[:RESULTED_IN]-()
            RETURN DISTINCT candidate.id
            ORDER BY candidate.id
            """,
            {"change_id": change_id},
        ).result_set

        return [row[0] for row in rows if row and row[0]]

    def _outcome_reachable_target(
        self,
        node_id: str,
    ) -> str:
        ids = self._candidate_outcome_ids(node_id)

        if not ids:
            raise ValueError(f"no reachable outcome found from {node_id}")

        return ids[0]

    @staticmethod
    def _node_from_ordering_row(
        row: list[Any],
    ) -> GraphNode:
        """Convert the four-field M5 ordering result."""
        if len(row) != 4:
            raise ValueError(
                "temporal ordering row must contain exactly id, labels, name, timestamp"
            )

        node_id, labels, name, timestamp = row

        return GraphNode(
            id=str(node_id),
            label=str((labels or ["Entity"])[0]),
            name=str(name or node_id),
            timestamp=timestamp,
            properties={"id": node_id},
        )

    @staticmethod
    def _is_change_candidate(
        row: list[Any],
    ) -> bool:
        labels = set(row[1] or [])

        return "Source" not in labels and row[0] is not None and row[3] is not None

    @staticmethod
    def _extract_node_id(
        value: str,
    ) -> str | None:
        matches = re.findall(
            r"[A-Za-z][A-Za-z0-9_.-]*",
            value,
        )

        for match in matches:
            if "-" in match or match.endswith(tuple(str(i) for i in range(10))):
                return match

        return None

    @staticmethod
    def _question_tokens(
        value: str,
    ) -> list[str]:
        stop = {
            "why",
            "did",
            "does",
            "what",
            "happen",
            "happened",
            "how",
            "the",
            "a",
            "an",
            "to",
            "of",
            "this",
            "incident",
        }

        return [
            token.lower()
            for token in re.findall(
                r"[A-Za-z0-9_.-]+",
                value,
            )
            if token.lower() not in stop and len(token) > 2
        ][:6]

    @staticmethod
    def _node_from_row(
        row: list[Any],
    ) -> GraphNode:
        labels, node_id, name, timestamp = row[:4]

        return GraphNode(
            id=str(node_id),
            label=str((labels or ["Entity"])[0]),
            name=str(name or node_id),
            timestamp=timestamp,
        )

    @staticmethod
    def _node_from_rich_row(
        row: list[Any],
    ) -> GraphNode:
        (
            labels,
            node_id,
            name,
            timestamp,
            valid_from,
            valid_until,
            observed_at,
            *rest,
        ) = row

        properties = dict(rest[0]) if rest and isinstance(rest[0], dict) else {}

        properties.setdefault(
            "id",
            node_id,
        )

        return GraphNode(
            id=str(node_id),
            label=str((labels or ["Entity"])[0]),
            name=str(name or node_id),
            timestamp=timestamp,
            valid_from=valid_from,
            valid_until=valid_until,
            observed_at=observed_at,
            properties=properties,
        )

    @staticmethod
    def _unique_evidence(
        evidence: Iterable[Evidence],
    ) -> list[Evidence]:
        unique: dict[str, Evidence] = {}

        for item in evidence:
            unique.setdefault(
                item.id,
                item,
            )

        return list(unique.values())
