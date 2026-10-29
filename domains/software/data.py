from __future__ import annotations

from datetime import datetime

from continuum.core.models import GraphEdge, GraphNode


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SoftwareData:
    def nodes(self) -> tuple[GraphNode, ...]:
        return (
            GraphNode(
                "commit-001",
                "Commit",
                "payments: upgrade gateway-sdk",
                timestamp=_dt("2026-08-01T09:00:00Z"),
                properties={"kind": "Commit"},
            ),
            GraphNode(
                "dependency-gateway-sdk",
                "Dependency",
                "gateway-sdk",
                properties={"kind": "Dependency"},
            ),
            GraphNode(
                "service-payments",
                "Service",
                "payments-service",
                properties={"kind": "Service"},
            ),
            GraphNode(
                "deployment-001",
                "Deployment",
                "payments deployment",
                timestamp=_dt("2026-08-01T09:20:00Z"),
                properties={"kind": "Deployment"},
            ),
            GraphNode(
                "config-001",
                "Configuration",
                "payments timeout configuration",
                timestamp=_dt("2026-08-01T10:30:00Z"),
                properties={"kind": "Configuration"},
            ),
            GraphNode(
                "metric-001",
                "Metric",
                "payments latency spike",
                timestamp=_dt("2026-08-01T09:45:00Z"),
                properties={"kind": "Metric"},
            ),
            GraphNode(
                "incident-001",
                "Incident",
                "INC-001 payment failures",
                timestamp=_dt("2026-08-01T10:00:00Z"),
                properties={"kind": "Incident"},
            ),
            GraphNode(
                "source-deploy",
                "Source",
                "deployment-record",
                properties={"record": "deployment-001"},
            ),
            GraphNode(
                "source-commit",
                "Source",
                "git-commit",
                properties={"record": "commit-001"},
            ),
        )

    def edges(self) -> tuple[GraphEdge, ...]:
        return (
            GraphEdge(
                "commit-001",
                "CHANGED",
                "dependency-gateway-sdk",
                timestamp=_dt("2026-08-01T09:00:00Z"),
                evidence_source_ids=("source-commit",),
            ),
            GraphEdge(
                "dependency-gateway-sdk",
                "DEPENDS_ON",
                "service-payments",
                timestamp=_dt("2026-08-01T09:00:00Z"),
            ),
            GraphEdge(
                "service-payments",
                "AFFECTS",
                "deployment-001",
                timestamp=_dt("2026-08-01T09:20:00Z"),
            ),
            GraphEdge(
                "deployment-001",
                "AFFECTS",
                "metric-001",
                timestamp=_dt("2026-08-01T09:20:00Z"),
            ),
            GraphEdge(
                "metric-001",
                "RESULTED_IN",
                "incident-001",
                timestamp=_dt("2026-08-01T10:00:00Z"),
            ),
            GraphEdge(
                "config-001",
                "AFFECTS",
                "metric-001",
                timestamp=_dt("2026-08-01T10:30:00Z"),
            ),
            GraphEdge("deployment-001", "SUPPORTED_BY", "source-deploy"),
            GraphEdge("commit-001", "SUPPORTED_BY", "source-commit"),
        )


SOFTWARE_DATA = SoftwareData()
