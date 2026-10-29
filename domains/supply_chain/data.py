from __future__ import annotations

from datetime import datetime

from continuum.core.models import GraphEdge, GraphNode


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SupplyChainData:
    def nodes(self) -> tuple[GraphNode, ...]:
        return (
            GraphNode(
                "supplier-001",
                "Supplier",
                "Acme Components",
                properties={"kind": "Supplier"},
            ),
            GraphNode(
                "component-001",
                "Component",
                "gateway controller",
                properties={"kind": "Component"},
            ),
            GraphNode(
                "factory-001", "Factory", "Plant A", properties={"kind": "Factory"}
            ),
            GraphNode(
                "shipment-001",
                "Shipment",
                "Shipment S-001",
                timestamp=_dt("2026-08-05T08:00:00Z"),
                properties={"kind": "Shipment"},
            ),
            GraphNode(
                "warehouse-001",
                "Warehouse",
                "West Warehouse",
                properties={"kind": "Warehouse"},
            ),
            GraphNode(
                "customer-001",
                "Customer",
                "Customer X",
                properties={"kind": "Customer"},
            ),
            GraphNode(
                "impact-001",
                "Impact",
                "Customer X delivery disruption",
                timestamp=_dt("2026-08-06T15:00:00Z"),
                properties={"kind": "Impact"},
            ),
            GraphNode(
                "source-shipment",
                "Source",
                "shipment-record",
                properties={"record": "shipment-001"},
            ),
        )

    def edges(self) -> tuple[GraphEdge, ...]:
        return (
            GraphEdge(
                "supplier-001",
                "OWNED_BY",
                "component-001",
                timestamp=_dt("2026-08-01T00:00:00Z"),
            ),
            GraphEdge(
                "component-001",
                "DEPENDS_ON",
                "factory-001",
                timestamp=_dt("2026-08-01T00:00:00Z"),
            ),
            GraphEdge(
                "factory-001",
                "AFFECTS",
                "shipment-001",
                timestamp=_dt("2026-08-05T08:00:00Z"),
            ),
            GraphEdge(
                "shipment-001",
                "AFFECTS",
                "warehouse-001",
                timestamp=_dt("2026-08-05T12:00:00Z"),
            ),
            GraphEdge(
                "warehouse-001",
                "AFFECTS",
                "customer-001",
                timestamp=_dt("2026-08-06T10:00:00Z"),
            ),
            GraphEdge(
                "customer-001",
                "RESULTED_IN",
                "impact-001",
                timestamp=_dt("2026-08-06T15:00:00Z"),
            ),
            GraphEdge("shipment-001", "SUPPORTED_BY", "source-shipment"),
        )


SUPPLY_CHAIN_DATA = SupplyChainData()
