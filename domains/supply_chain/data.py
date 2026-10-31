from __future__ import annotations

from datetime import UTC, datetime

from continuum.core.models import GraphEdge, GraphNode


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


class SupplyChainData:
    """Deterministic M15 supply-chain world with competing and invalid paths."""

    def nodes(self) -> tuple[GraphNode, ...]:
        nodes: list[GraphNode] = []

        specs = [
            ("supplier-001", "Supplier", "Acme Components"),
            ("component-001", "Component", "Power controller"),
            ("factory-001", "Factory", "Plant A"),
            ("shipment-001", "Shipment", "Shipment S-001"),
            ("supplier-002", "Supplier", "Northstar Components"),
            ("component-002", "Component", "Power controller alternate"),
            ("factory-002", "Factory", "Plant B"),
            ("shipment-002", "Shipment", "Shipment S-002"),
            ("supplier-003", "Supplier", "Delayed Components"),
            ("component-003", "Component", "Delayed controller"),
            ("factory-003", "Factory", "Plant C"),
            ("shipment-003", "Shipment", "Shipment S-003"),
            ("supplier-999", "Supplier", "Unrelated Supplier"),
            ("component-999", "Component", "Unrelated component"),
            ("factory-999", "Factory", "Unrelated Plant"),
        ]

        shipment_timestamps = {
            "shipment-001": "2026-08-05T12:00:00Z",
            "shipment-002": "2026-08-05T13:00:00Z",
            "shipment-003": "2026-08-07T12:00:00Z",
        }

        for node_id, label, name in specs:
            timestamp = (
                _dt(shipment_timestamps[node_id])
                if node_id in shipment_timestamps
                else None
            )

            nodes.append(
                GraphNode(
                    node_id,
                    label,
                    name,
                    timestamp=timestamp,
                    properties={"kind": label},
                )
            )

        nodes.extend(
            [
                GraphNode(
                    "warehouse-001",
                    "Warehouse",
                    "West Warehouse",
                    properties={"kind": "Warehouse"},
                ),
                GraphNode(
                    "account-001",
                    "Customer",
                    "Account X",
                    properties={
                        "kind": "Customer",
                        "display_name": "Account X",
                    },
                ),
                GraphNode(
                    "impact-001",
                    "Impact",
                    "Customer X affected",
                    timestamp=_dt("2026-08-06T15:00:00Z"),
                    properties={
                        "kind": "Impact",
                        "display_name": "Customer X affected",
                    },
                ),
            ]
        )

        source_specs = [
            (
                "source-supplier-001",
                "supplier-registry",
                "supplier-001",
                "supplier owns component-001",
            ),
            (
                "source-component-001",
                "factory-registry",
                "component-001",
                "component-001 assigned to factory-001",
            ),
            (
                "source-factory-001",
                "shipment-system",
                "shipment-001",
                "factory-001 produced shipment-001",
            ),
            (
                "source-shipment-001",
                "warehouse-system",
                "shipment-001",
                "shipment-001 received at warehouse-001",
            ),
            (
                "source-warehouse",
                "fulfillment-system",
                "account-001",
                "warehouse-001 allocated inventory to Customer X",
            ),
            (
                "source-impact",
                "customer-support",
                "impact-001",
                "Customer X affected",
            ),
            (
                "source-supplier-002",
                "supplier-registry",
                "supplier-002",
                "supplier-002 owns component-002",
            ),
            (
                "source-component-002",
                "factory-registry",
                "component-002",
                "component-002 assigned to factory-002",
            ),
            (
                "source-factory-002",
                "shipment-system",
                "shipment-002",
                "factory-002 produced shipment-002",
            ),
            (
                "source-shipment-002",
                "warehouse-system",
                "shipment-002",
                "shipment-002 received at warehouse-001",
            ),
            (
                "source-supplier-003",
                "supplier-registry",
                "supplier-003",
                "supplier-003 owns component-003",
            ),
            (
                "source-component-003",
                "factory-registry",
                "component-003",
                "component-003 assigned to factory-003",
            ),
            (
                "source-factory-003",
                "shipment-system",
                "shipment-003",
                "factory-003 produced shipment-003",
            ),
            (
                "source-shipment-003",
                "warehouse-system",
                "shipment-003",
                "shipment-003 received after the customer impact",
            ),
            (
                "source-distractor",
                "supplier-registry",
                "supplier-999",
                "unrelated supplier record",
            ),
            (
                "source-distractor-component",
                "factory-registry",
                "component-999",
                "unrelated component record",
            ),
            (
                "source-distractor-factory",
                "shipment-system",
                "factory-999",
                "unrelated factory record",
            ),
        ]

        observed = {
            "source-supplier-001": "2026-08-01T00:00:00Z",
            "source-component-001": "2026-08-01T01:00:00Z",
            "source-factory-001": "2026-08-05T08:00:00Z",
            "source-shipment-001": "2026-08-05T12:00:00Z",
            "source-warehouse": "2026-08-06T10:00:00Z",
            "source-impact": "2026-08-06T15:00:00Z",
            "source-supplier-002": "2026-08-01T02:00:00Z",
            "source-component-002": "2026-08-01T03:00:00Z",
            "source-factory-002": "2026-08-05T09:00:00Z",
            "source-shipment-002": "2026-08-05T13:00:00Z",
            "source-supplier-003": "2026-08-01T04:00:00Z",
            "source-component-003": "2026-08-01T05:00:00Z",
            "source-factory-003": "2026-08-07T08:00:00Z",
            "source-shipment-003": "2026-08-07T12:00:00Z",
            "source-distractor": "2026-08-01T00:00:00Z",
            "source-distractor-component": "2026-08-01T00:00:00Z",
            "source-distractor-factory": "2026-08-01T00:00:00Z",
        }

        for source_id, system, record, span in source_specs:
            nodes.append(
                GraphNode(
                    source_id,
                    "Source",
                    span,
                    observed_at=_dt(observed[source_id]),
                    properties={
                        "kind": "Source",
                        "system": system,
                        "record": record,
                        "span": span,
                        "status": "OBSERVED",
                    },
                )
            )

        return tuple(nodes)

    def edges(self) -> tuple[GraphEdge, ...]:
        def e(
            source: str,
            rel: str,
            target: str,
            ts: str,
            evidence: str,
        ) -> GraphEdge:
            return GraphEdge(
                source,
                rel,
                target,
                timestamp=_dt(ts),
                evidence_source_ids=(evidence,),
            )

        return (
            # Primary supply-chain explanation.
            e(
                "supplier-001",
                "OWNED_BY",
                "component-001",
                "2026-08-01T00:00:00Z",
                "source-supplier-001",
            ),
            e(
                "component-001",
                "DEPENDS_ON",
                "factory-001",
                "2026-08-01T01:00:00Z",
                "source-component-001",
            ),
            e(
                "factory-001",
                "AFFECTS",
                "shipment-001",
                "2026-08-05T08:00:00Z",
                "source-factory-001",
            ),
            e(
                "shipment-001",
                "AFFECTS",
                "warehouse-001",
                "2026-08-05T12:00:00Z",
                "source-shipment-001",
            ),
            e(
                "warehouse-001",
                "AFFECTS",
                "account-001",
                "2026-08-06T10:00:00Z",
                "source-warehouse",
            ),
            e(
                "account-001",
                "RESULTED_IN",
                "impact-001",
                "2026-08-06T15:00:00Z",
                "source-impact",
            ),
            # Alternative supply-chain explanation.
            e(
                "supplier-002",
                "OWNED_BY",
                "component-002",
                "2026-08-01T02:00:00Z",
                "source-supplier-002",
            ),
            e(
                "component-002",
                "DEPENDS_ON",
                "factory-002",
                "2026-08-01T03:00:00Z",
                "source-component-002",
            ),
            e(
                "factory-002",
                "AFFECTS",
                "shipment-002",
                "2026-08-05T09:00:00Z",
                "source-factory-002",
            ),
            e(
                "shipment-002",
                "AFFECTS",
                "warehouse-001",
                "2026-08-05T13:00:00Z",
                "source-shipment-002",
            ),
            # Temporally conflicting explanation.
            e(
                "supplier-003",
                "OWNED_BY",
                "component-003",
                "2026-08-01T04:00:00Z",
                "source-supplier-003",
            ),
            e(
                "component-003",
                "DEPENDS_ON",
                "factory-003",
                "2026-08-01T05:00:00Z",
                "source-component-003",
            ),
            e(
                "factory-003",
                "AFFECTS",
                "shipment-003",
                "2026-08-07T08:00:00Z",
                "source-factory-003",
            ),
            e(
                "shipment-003",
                "AFFECTS",
                "warehouse-001",
                "2026-08-07T12:00:00Z",
                "source-shipment-003",
            ),
            # Entity-level provenance.
            GraphEdge(
                "supplier-001",
                "SUPPORTED_BY",
                "source-supplier-001",
            ),
            GraphEdge(
                "component-001",
                "SUPPORTED_BY",
                "source-component-001",
            ),
            GraphEdge(
                "factory-001",
                "SUPPORTED_BY",
                "source-factory-001",
            ),
            GraphEdge(
                "shipment-001",
                "SUPPORTED_BY",
                "source-shipment-001",
            ),
            GraphEdge(
                "warehouse-001",
                "SUPPORTED_BY",
                "source-warehouse",
            ),
            GraphEdge(
                "impact-001",
                "SUPPORTED_BY",
                "source-impact",
            ),
            GraphEdge(
                "supplier-002",
                "SUPPORTED_BY",
                "source-supplier-002",
            ),
            GraphEdge(
                "component-002",
                "SUPPORTED_BY",
                "source-component-002",
            ),
            GraphEdge(
                "factory-002",
                "SUPPORTED_BY",
                "source-factory-002",
            ),
            GraphEdge(
                "shipment-002",
                "SUPPORTED_BY",
                "source-shipment-002",
            ),
            GraphEdge(
                "supplier-003",
                "SUPPORTED_BY",
                "source-supplier-003",
            ),
            GraphEdge(
                "component-003",
                "SUPPORTED_BY",
                "source-component-003",
            ),
            GraphEdge(
                "factory-003",
                "SUPPORTED_BY",
                "source-factory-003",
            ),
            GraphEdge(
                "supplier-999",
                "SUPPORTED_BY",
                "source-distractor",
            ),
            GraphEdge(
                "component-999",
                "SUPPORTED_BY",
                "source-distractor-component",
            ),
            GraphEdge(
                "factory-999",
                "SUPPORTED_BY",
                "source-distractor-factory",
            ),
        )


SUPPLY_CHAIN_DATA = SupplyChainData()
