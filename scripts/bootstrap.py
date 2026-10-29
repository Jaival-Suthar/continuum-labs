from continuum.graph import GraphClient, initialize_graph
from continuum.graph.seed import seed_software_world


def main() -> None:
    client = initialize_graph(GraphClient())
    seed_software_world(client)
    print("Continuum FalkorDB foundation ready.")


if __name__ == "__main__":
    main()
