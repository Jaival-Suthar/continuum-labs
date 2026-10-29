from continuum.graph import GraphClient


def main() -> None:
    client = GraphClient()
    client.ping()
    print(f"FalkorDB OK: graph={client.config.graph_name}")


if __name__ == "__main__":
    main()
