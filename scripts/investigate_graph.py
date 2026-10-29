from continuum.graph import GraphClient, GraphTraversal
from continuum.graph.seed import seed_software_world


def main() -> None:
    client = seed_software_world(GraphClient())
    traversal = GraphTraversal(client)

    print("Connected to incident-001:")
    for row in traversal.neighbors("incident-001"):
        print(row)

    print("\nPaths from commit-001 to incident-001:")
    for row in traversal.paths_between("commit-001", "incident-001"):
        print(row)

    print("\nEvidence for commit-001 -> dependency-gateway-sdk:")
    for row in traversal.relationship_evidence("commit-001", "dependency-gateway-sdk"):
        print(row)


if __name__ == "__main__":
    main()
