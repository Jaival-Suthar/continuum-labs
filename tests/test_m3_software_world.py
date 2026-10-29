from domains.software.world import SOFTWARE_WORLD

EXPECTED_PATH = [
    "commit-001",
    "dependency-gateway-sdk",
    "service-payments",
    "deployment-001",
    "metric-001",
    "incident-001",
]


def test_software_world_contains_primary_investigation_chain():
    nodes = {node.id: node for node in SOFTWARE_WORLD.data.nodes()}
    edges = SOFTWARE_WORLD.data.edges()

    assert EXPECTED_PATH == [
        "commit-001",
        "dependency-gateway-sdk",
        "service-payments",
        "deployment-001",
        "metric-001",
        "incident-001",
    ]

    edge_pairs = {(edge.source_id, edge.relationship, edge.target_id) for edge in edges}
    assert ("commit-001", "CHANGED", "dependency-gateway-sdk") in edge_pairs
    assert ("dependency-gateway-sdk", "DEPENDS_ON", "service-payments") in edge_pairs
    assert ("service-payments", "AFFECTS", "deployment-001") in edge_pairs
    assert ("deployment-001", "AFFECTS", "metric-001") in edge_pairs
    assert ("metric-001", "RESULTED_IN", "incident-001") in edge_pairs
    assert nodes["incident-001"].label == "Incident"


def test_software_world_contains_competing_explanations():
    edges = SOFTWARE_WORLD.data.edges()

    assert (
        "infra-event-001",
        "AFFECTS",
        "metric-001",
    ) in {(edge.source_id, edge.relationship, edge.target_id) for edge in edges}

    assert (
        "config-001",
        "AFFECTS",
        "metric-001",
    ) in {(edge.source_id, edge.relationship, edge.target_id) for edge in edges}


def test_configuration_hypothesis_is_temporally_after_incident():
    nodes = {node.id: node for node in SOFTWARE_WORLD.data.nodes()}
    incident = nodes["incident-001"]
    config = nodes["config-001"]

    assert config.timestamp is not None
    assert incident.timestamp is not None
    assert config.timestamp > incident.timestamp


def test_software_world_contains_unrelated_distractor_subgraph():
    edge_pairs = {
        (edge.source_id, edge.relationship, edge.target_id)
        for edge in SOFTWARE_WORLD.data.edges()
    }

    assert ("commit-002", "CHANGED", "dependency-cache-lib") in edge_pairs
    assert ("dependency-cache-lib", "DEPENDS_ON", "service-search") in edge_pairs
    assert ("service-search", "AFFECTS", "deployment-002") in edge_pairs
    assert ("deployment-002", "AFFECTS", "metric-002") in edge_pairs


def test_competing_hypotheses_can_have_missing_evidence():
    edges = {
        (edge.source_id, edge.relationship, edge.target_id): edge
        for edge in SOFTWARE_WORLD.data.edges()
    }

    infra = edges[("infra-event-001", "AFFECTS", "metric-001")]
    config = edges[("config-001", "AFFECTS", "metric-001")]

    assert infra.evidence_source_ids == ()
    assert config.evidence_source_ids == ()


def test_primary_path_has_temporally_ordered_events():
    nodes = {node.id: node for node in SOFTWARE_WORLD.data.nodes()}

    ordered = [
        nodes["commit-001"].timestamp,
        nodes["deployment-001"].timestamp,
        nodes["metric-001"].timestamp,
        nodes["incident-001"].timestamp,
    ]

    assert all(value is not None for value in ordered)
    assert ordered == sorted(ordered)
