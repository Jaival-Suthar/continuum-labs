from __future__ import annotations

from datetime import UTC

from domains.supply_chain.data import SUPPLY_CHAIN_DATA
from domains.supply_chain.world import SUPPLY_CHAIN_WORLD


def test_m15_world_validates():
    SUPPLY_CHAIN_WORLD.validate()


def test_m15_has_required_domain_labels():
    labels = {node.label for node in SUPPLY_CHAIN_DATA.nodes()}
    assert {
        "Supplier",
        "Component",
        "Factory",
        "Shipment",
        "Warehouse",
        "Customer",
        "Impact",
    } <= labels


def test_m15_has_primary_six_hop_chain():
    edges = {
        (e.source_id, e.relationship, e.target_id) for e in SUPPLY_CHAIN_DATA.edges()
    }
    chain = (
        ("supplier-001", "OWNED_BY", "component-001"),
        ("component-001", "DEPENDS_ON", "factory-001"),
        ("factory-001", "AFFECTS", "shipment-001"),
        ("shipment-001", "AFFECTS", "warehouse-001"),
        ("warehouse-001", "AFFECTS", "account-001"),
        ("account-001", "RESULTED_IN", "impact-001"),
    )
    assert all(item in edges for item in chain)


def test_m15_has_independent_alternative_upstream_chain():
    edges = {(e.source_id, e.target_id) for e in SUPPLY_CHAIN_DATA.edges()}
    assert ("supplier-001", "component-001") in edges
    assert ("supplier-002", "component-002") in edges
    assert ("factory-001", "shipment-001") in edges
    assert ("factory-002", "shipment-002") in edges


def test_m15_no_single_source_contains_complete_primary_chain():
    primary_ids = {
        "supplier-001",
        "component-001",
        "factory-001",
        "shipment-001",
        "warehouse-001",
        "account-001",
        "impact-001",
    }
    for edge in SUPPLY_CHAIN_DATA.edges():
        if edge.source_id in primary_ids and edge.target_id in primary_ids:
            assert len(edge.evidence_source_ids) == 1


def test_m15_conflict_is_later_than_customer_impact():
    edges = {(e.source_id, e.target_id): e for e in SUPPLY_CHAIN_DATA.edges()}
    assert (
        edges[("shipment-003", "warehouse-001")].timestamp
        > edges[("account-001", "impact-001")].timestamp
    )


def test_m15_timestamps_are_timezone_aware():
    for node in SUPPLY_CHAIN_DATA.nodes():
        for value in (
            node.timestamp,
            node.valid_from,
            node.valid_until,
            node.observed_at,
        ):
            if value is not None:
                assert value.tzinfo is not None and value.utcoffset() is not None
    for edge in SUPPLY_CHAIN_DATA.edges():
        if edge.timestamp is not None:
            assert edge.timestamp.tzinfo is UTC


def test_m15_adapter_exposes_only_loader_contract():
    assert callable(SUPPLY_CHAIN_DATA.nodes)
    assert callable(SUPPLY_CHAIN_DATA.edges)
    assert not hasattr(SUPPLY_CHAIN_DATA, "investigate")
