from __future__ import annotations

from continuum.core.models import InvestigationResult
from continuum.core.world import World
from continuum.graph.client import GraphClient


class Investigator:
    """Domain-independent investigation boundary.

    The investigator accepts a World contract rather than branching on domains.
    Investigation primitives are added in later milestones.
    """

    def __init__(self, graph: GraphClient, world: World | None = None):
        self.graph = graph
        self.world = world

    def investigate(
        self, question: str, world: World | None = None
    ) -> InvestigationResult:
        active_world = world or self.world
        if active_world is not None:
            active_world.validate()

        trace = ["investigation_started"]
        if active_world is not None:
            trace.append(f"world={active_world.name}")

        return InvestigationResult(question=question, trace=trace)
