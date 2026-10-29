from __future__ import annotations

from datetime import datetime

from continuum.core.models import GraphEdge, GraphNode


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SoftwareData:
    """Controlled software investigation world for M3.

    The dataset intentionally contains:
    - one evidence-backed six-node explanation path,
    - a temporally valid but weakly evidenced infrastructure alternative,
    - a temporally invalid configuration alternative,
    - unrelated graph distractors,
    - and missing evidence on competing hypotheses.
    """

    def nodes(self) -> tuple[GraphNode, ...]:
        return (
            # Primary explanation.
            GraphNode(
                "commit-001",
                "Commit",
                "payments: upgrade gateway-sdk",
                timestamp=_dt("2026-08-01T09:00:00Z"),
                properties={
                    "kind": "Commit",
                    "repository": "payments",
                    "author": "alice",
                    "change_type": "dependency_update",
                },
            ),
            GraphNode(
                "dependency-gateway-sdk",
                "Dependency",
                "gateway-sdk",
                properties={
                    "kind": "Dependency",
                    "version_before": "4.8.1",
                    "version_after": "4.9.0",
                },
            ),
            GraphNode(
                "service-payments",
                "Service",
                "payments-service",
                properties={"kind": "Service", "owner": "payments-team"},
            ),
            GraphNode(
                "deployment-001",
                "Deployment",
                "payments deployment 2026-08-01",
                timestamp=_dt("2026-08-01T09:20:00Z"),
                properties={
                    "kind": "Deployment",
                    "environment": "production",
                    "commit_id": "commit-001",
                },
            ),
            GraphNode(
                "metric-001",
                "Metric",
                "payments p99 latency spike",
                timestamp=_dt("2026-08-01T09:45:00Z"),
                properties={
                    "kind": "Metric",
                    "metric": "http_request_duration_p99",
                    "baseline_ms": 180,
                    "observed_ms": 940,
                },
            ),
            GraphNode(
                "incident-001",
                "Incident",
                "INC-001 payment failures",
                timestamp=_dt("2026-08-01T10:00:00Z"),
                properties={
                    "kind": "Incident",
                    "severity": "SEV-1",
                    "status": "resolved",
                },
            ),
            # Alternative hypothesis: infrastructure.
            GraphNode(
                "infra-event-001",
                "InfrastructureEvent",
                "payments node pool saturation",
                timestamp=_dt("2026-08-01T09:35:00Z"),
                properties={
                    "kind": "InfrastructureEvent",
                    "hypothesis": "infrastructure",
                    "status": "observed",
                },
            ),
            # Alternative hypothesis: configuration, deliberately after the outcome.
            GraphNode(
                "config-001",
                "Configuration",
                "payments timeout configuration changed",
                timestamp=_dt("2026-08-01T10:30:00Z"),
                properties={
                    "kind": "Configuration",
                    "hypothesis": "configuration",
                    "previous_value": "2s",
                    "new_value": "5s",
                },
            ),
            # Distractor subgraph: plausible software activity unrelated to INC-001.
            GraphNode(
                "commit-002",
                "Commit",
                "search: optimize cache lookup",
                timestamp=_dt("2026-08-01T08:40:00Z"),
                properties={
                    "kind": "Commit",
                    "repository": "search",
                    "author": "bob",
                },
            ),
            GraphNode(
                "dependency-cache-lib",
                "Dependency",
                "cache-lib",
                properties={"kind": "Dependency"},
            ),
            GraphNode(
                "service-search",
                "Service",
                "search-service",
                properties={"kind": "Service", "owner": "search-team"},
            ),
            GraphNode(
                "deployment-002",
                "Deployment",
                "search deployment 2026-08-01",
                timestamp=_dt("2026-08-01T08:55:00Z"),
                properties={"kind": "Deployment", "environment": "production"},
            ),
            GraphNode(
                "metric-002",
                "Metric",
                "search cache hit-rate improvement",
                timestamp=_dt("2026-08-01T09:10:00Z"),
                properties={
                    "kind": "Metric",
                    "metric": "cache_hit_rate",
                    "observed_percent": 96,
                },
            ),
            # Unrelated operational event.
            GraphNode(
                "infra-event-002",
                "InfrastructureEvent",
                "search node restart",
                timestamp=_dt("2026-08-01T09:05:00Z"),
                properties={"kind": "InfrastructureEvent"},
            ),
            # Evidence/source records. Competing hypotheses intentionally lack
            # dedicated source records so later milestones can demonstrate gaps.
            GraphNode(
                "source-commit-001",
                "Source",
                "git commit record abc123",
                properties={
                    "kind": "Source",
                    "system": "git",
                    "record": "abc123",
                },
            ),
            GraphNode(
                "source-deployment-001",
                "Source",
                "production deployment record deploy-001",
                properties={
                    "kind": "Source",
                    "system": "deployment",
                    "record": "deploy-001",
                },
            ),
            GraphNode(
                "source-metric-001",
                "Source",
                "observability record metric-001",
                properties={
                    "kind": "Source",
                    "system": "observability",
                    "record": "metric-001",
                },
            ),
            GraphNode(
                "source-incident-001",
                "Source",
                "incident record INC-001",
                properties={
                    "kind": "Source",
                    "system": "incident",
                    "record": "INC-001",
                },
            ),
        )

    def edges(self) -> tuple[GraphEdge, ...]:
        return (
            # Ground-truth multi-hop path:
            # commit -> dependency -> service -> deployment -> metric -> incident
            GraphEdge(
                "commit-001",
                "CHANGED",
                "dependency-gateway-sdk",
                timestamp=_dt("2026-08-01T09:00:00Z"),
                evidence_source_ids=("source-commit-001",),
                properties={"role": "ground_truth"},
            ),
            GraphEdge(
                "dependency-gateway-sdk",
                "DEPENDS_ON",
                "service-payments",
                timestamp=_dt("2026-08-01T09:00:00Z"),
                properties={"role": "dependency_propagation"},
            ),
            GraphEdge(
                "service-payments",
                "AFFECTS",
                "deployment-001",
                timestamp=_dt("2026-08-01T09:20:00Z"),
                evidence_source_ids=("source-deployment-001",),
                properties={"role": "ground_truth"},
            ),
            GraphEdge(
                "deployment-001",
                "AFFECTS",
                "metric-001",
                timestamp=_dt("2026-08-01T09:20:00Z"),
                evidence_source_ids=("source-deployment-001",),
                properties={"role": "ground_truth"},
            ),
            GraphEdge(
                "metric-001",
                "RESULTED_IN",
                "incident-001",
                timestamp=_dt("2026-08-01T10:00:00Z"),
                evidence_source_ids=("source-metric-001", "source-incident-001"),
                properties={"role": "ground_truth"},
            ),
            # Temporally valid alternative explanation, deliberately missing
            # direct evidence.
            GraphEdge(
                "infra-event-001",
                "AFFECTS",
                "metric-001",
                timestamp=_dt("2026-08-01T09:35:00Z"),
                properties={
                    "role": "alternative_hypothesis",
                    "hypothesis": "infrastructure",
                },
            ),
            # Temporally invalid alternative explanation: after incident.
            GraphEdge(
                "config-001",
                "AFFECTS",
                "metric-001",
                timestamp=_dt("2026-08-01T10:30:00Z"),
                properties={
                    "role": "temporal_trap",
                    "hypothesis": "configuration",
                },
            ),
            # Distractor subgraph.
            GraphEdge(
                "commit-002",
                "CHANGED",
                "dependency-cache-lib",
                timestamp=_dt("2026-08-01T08:40:00Z"),
                properties={"role": "distractor"},
            ),
            GraphEdge(
                "dependency-cache-lib",
                "DEPENDS_ON",
                "service-search",
                timestamp=_dt("2026-08-01T08:40:00Z"),
                properties={"role": "distractor"},
            ),
            GraphEdge(
                "service-search",
                "AFFECTS",
                "deployment-002",
                timestamp=_dt("2026-08-01T08:55:00Z"),
                properties={"role": "distractor"},
            ),
            GraphEdge(
                "deployment-002",
                "AFFECTS",
                "metric-002",
                timestamp=_dt("2026-08-01T08:55:00Z"),
                properties={"role": "distractor"},
            ),
            GraphEdge(
                "infra-event-002",
                "AFFECTS",
                "metric-002",
                timestamp=_dt("2026-08-01T09:05:00Z"),
                properties={"role": "distractor"},
            ),
            # Explicit source relationships for the evidence-backed path.
            GraphEdge("commit-001", "SUPPORTED_BY", "source-commit-001"),
            GraphEdge("deployment-001", "SUPPORTED_BY", "source-deployment-001"),
            GraphEdge("metric-001", "SUPPORTED_BY", "source-metric-001"),
            GraphEdge("incident-001", "SUPPORTED_BY", "source-incident-001"),
        )


SOFTWARE_DATA = SoftwareData()
