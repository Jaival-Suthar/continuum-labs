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
                "source-supplier",
                "Source",
                "supplier ownership record",
                properties={
                    "kind": "Source",
                    "system": "supplier-registry",
                    "record": "supplier-001",
                    "span": "supplier component ownership",
                    "status": "OBSERVED",
                },
                observed_at=_dt("2026-08-01T00:00:00Z"),
            ),
            GraphNode(
                "source-component",
                "Source",
                "component factory dependency record",
                properties={
                    "kind": "Source",
                    "system": "factory-registry",
                    "record": "component-001",
                    "span": "component assigned to factory",
                    "status": "OBSERVED",
                },
                observed_at=_dt("2026-08-01T00:00:00Z"),
            ),
            GraphNode(
                "source-factory-shipment",
                "Source",
                "factory shipment record",
                properties={
                    "kind": "Source",
                    "system": "shipment-system",
                    "record": "shipment-001",
                    "span": "shipment origin at factory",
                    "status": "OBSERVED",
                },
                observed_at=_dt("2026-08-05T08:00:00Z"),
            ),
            GraphNode(
                "source-shipment-warehouse",
                "Source",
                "warehouse receipt record",
                properties={
                    "kind": "Source",
                    "system": "warehouse-system",
                    "record": "shipment-001-receipt",
                    "span": "shipment received by warehouse",
                    "status": "OBSERVED",
                },
                observed_at=_dt("2026-08-05T12:00:00Z"),
            ),
            GraphNode(
                "source-warehouse-customer",
                "Source",
                "customer fulfillment record",
                properties={
                    "kind": "Source",
                    "system": "fulfillment-system",
                    "record": "customer-001",
                    "span": "warehouse allocation to customer",
                    "status": "OBSERVED",
                },
                observed_at=_dt("2026-08-06T10:00:00Z"),
            ),
            GraphNode(
                "source-impact",
                "Source",
                "customer impact record",
                properties={
                    "kind": "Source",
                    "system": "customer-support",
                    "record": "impact-001",
                    "span": "customer delivery disruption",
                    "status": "OBSERVED",
                },
                observed_at=_dt("2026-08-06T15:00:00Z"),
            ),
            GraphNode(
                "source-shipment",
                "Source",
                "shipment-record",
                properties={
                    "kind": "Source",
                    "system": "shipment-system",
                    "record": "shipment-001",
                    "span": "shipment master record",
                    "status": "OBSERVED",
                },
                observed_at=_dt("2026-08-05T08:00:00Z"),
            ),
        )

    def edges(self) -> tuple[GraphEdge, ...]:
        return (
            GraphEdge(
                "supplier-001",
                "OWNED_BY",
                "component-001",
                timestamp=_dt("2026-08-01T00:00:00Z"),
                evidence_source_ids=("source-supplier",),
            ),
            GraphEdge(
                "component-001",
                "DEPENDS_ON",
                "factory-001",
                timestamp=_dt("2026-08-01T00:00:00Z"),
                evidence_source_ids=("source-component",),
            ),
            GraphEdge(
                "factory-001",
                "AFFECTS",
                "shipment-001",
                timestamp=_dt("2026-08-05T08:00:00Z"),
                evidence_source_ids=("source-factory-shipment",),
            ),
            GraphEdge(
                "shipment-001",
                "AFFECTS",
                "warehouse-001",
                timestamp=_dt("2026-08-05T12:00:00Z"),
                evidence_source_ids=("source-shipment-warehouse",),
            ),
            GraphEdge(
                "warehouse-001",
                "AFFECTS",
                "customer-001",
                timestamp=_dt("2026-08-06T10:00:00Z"),
                evidence_source_ids=("source-warehouse-customer",),
            ),
            GraphEdge(
                "customer-001",
                "RESULTED_IN",
                "impact-001",
                timestamp=_dt("2026-08-06T15:00:00Z"),
                evidence_source_ids=("source-impact",),
            ),
            GraphEdge("supplier-001", "SUPPORTED_BY", "source-supplier"),
            GraphEdge("component-001", "SUPPORTED_BY", "source-component"),
            GraphEdge("factory-001", "SUPPORTED_BY", "source-factory-shipment"),
            GraphEdge("shipment-001", "SUPPORTED_BY", "source-shipment"),
            GraphEdge("shipment-001", "SUPPORTED_BY", "source-shipment-warehouse"),
            GraphEdge("warehouse-001", "SUPPORTED_BY", "source-warehouse-customer"),
            GraphEdge("customer-001", "SUPPORTED_BY", "source-impact"),
        )


SUPPLY_CHAIN_DATA = SupplyChainData()
