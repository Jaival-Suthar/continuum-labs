from continuum.graph import GraphClient, GraphTraversal, initialize_graph
from continuum.graph.provenance import relationship_with_evidence
from continuum.graph.seed import seed_software_world


def main() -> None:
    client = initialize_graph(GraphClient())
    seed_software_world(client)
    traversal = GraphTraversal(client)

    connected = traversal.neighbors("incident-001")
    paths = traversal.paths_between("commit-001", "incident-001")
    preceding = traversal.preceding("incident-001", "2026-08-01T10:00:00Z")
    evidence = relationship_with_evidence(
        client, "commit-001", "dependency-gateway-sdk"
    )

    print("M1 foundation check")
    print(f"connected_to_incident={len(connected)}")
    print(f"commit_to_incident_paths={len(paths)}")
    print(f"preceding_incident_records={len(preceding)}")
    print(f"relationships_with_provenance={len(evidence)}")


if __name__ == "__main__":
    main()
