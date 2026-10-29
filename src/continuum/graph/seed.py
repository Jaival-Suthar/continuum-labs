from __future__ import annotations

from continuum.graph.client import GraphClient

SEED_QUERY = """
CREATE
  (commit:Change {id:'commit-001', name:'payments: upgrade gateway-sdk', timestamp:'2026-08-01T09:00:00Z'}),
  (dependency:Entity {id:'dependency-gateway-sdk', name:'gateway-sdk'}),
  (service:Entity {id:'service-payments', name:'payments-service'}),
  (deployment:Event {id:'deployment-001', name:'payments deployment', timestamp:'2026-08-01T09:20:00Z'}),
  (config:Change {id:'config-001', name:'payments timeout configuration', timestamp:'2026-08-01T10:30:00Z'}),
  (metric:Observation {id:'metric-001', name:'payments latency spike', timestamp:'2026-08-01T09:45:00Z'}),
  (incident:Outcome {id:'incident-001', name:'INC-001 payment failures', timestamp:'2026-08-01T10:00:00Z'}),
  (source:Source {id:'source-deploy', name:'deployment-record', record:'deployment-001'}),
  (source2:Source {id:'source-commit', name:'git-commit', record:'commit-001'}),
  (commit)-[:CHANGED {timestamp:'2026-08-01T09:00:00Z'}]->(dependency),
  (dependency)-[:DEPENDS_ON {timestamp:'2026-08-01T09:00:00Z'}]->(service),
  (service)-[:AFFECTS {timestamp:'2026-08-01T09:20:00Z'}]->(deployment),
  (deployment)-[:AFFECTS {timestamp:'2026-08-01T09:20:00Z'}]->(metric),
  (metric)-[:RESULTED_IN {timestamp:'2026-08-01T10:00:00Z'}]->(incident),
  (config)-[:AFFECTS {timestamp:'2026-08-01T10:30:00Z'}]->(metric),
  (deployment)-[:SUPPORTED_BY]->(source),
  (commit)-[:SUPPORTED_BY]->(source2)
"""


def seed_software_world(client: GraphClient | None = None) -> GraphClient:
    client = client or GraphClient()
    client.reset()
    client.query(SEED_QUERY)
    return client


if __name__ == "__main__":
    seed_software_world()
    print("Seeded Continuum software investigation graph.")
