from continuum.core.models import InvestigationResult
from continuum.graph.client import GraphClient


class Investigator:
    """Domain-independent investigation engine.

    Domain-specific ontology/schema/data belong under domains/.
    """

    def __init__(self, graph: GraphClient):
        self.graph = graph

    def investigate(self, question: str) -> InvestigationResult:
        # M1/M2 foundation: orchestration will be implemented incrementally.
        return InvestigationResult(
            question=question,
            trace=["investigation_started"],
        )
