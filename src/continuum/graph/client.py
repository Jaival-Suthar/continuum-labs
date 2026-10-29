from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from falkordb import FalkorDB


@dataclass(frozen=True)
class GraphConfig:
    host: str = "localhost"
    port: int = 6379
    graph_name: str = "continuum"


class GraphClient:
    """Small infrastructure boundary around the official FalkorDB client."""

    def __init__(self, config: GraphConfig | None = None):
        self.config = config or GraphConfig()
        self.db = FalkorDB(host=self.config.host, port=self.config.port)
        self.graph = self.db.select_graph(self.config.graph_name)

    def query(self, cypher: str, params: dict[str, Any] | None = None):
        return self.graph.query(cypher, params or {})

    def read(self, cypher: str, params: dict[str, Any] | None = None):
        return self.graph.ro_query(cypher, params or {})

    def ping(self) -> bool:
        self.query("RETURN 1 AS ok")
        return True

    def execute_many(self, queries: Iterable[str]) -> None:
        for query in queries:
            self.query(query)

    def reset(self) -> None:
        self.query("MATCH (n) DETACH DELETE n")
