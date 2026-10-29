from falkordb import FalkorDB


class GraphClient:
    def __init__(self, host: str = "localhost", port: int = 6379, graph_name: str = "continuum"):
        self.db = FalkorDB(host=host, port=port)
        self.graph = self.db.select_graph(graph_name)

    def query(self, cypher: str, params: dict | None = None):
        return self.graph.query(cypher, params or {})
