from continuum.cli.output import header, info, success
from continuum.graph import GraphClient


def main() -> None:
    client = GraphClient()
    client.ping()

    header("SYSTEM", "FalkorDB connectivity")
    info("Graph", client.config.graph_name)
    info("Status", "Connected")
    success("FalkorDB")


if __name__ == "__main__":
    main()
