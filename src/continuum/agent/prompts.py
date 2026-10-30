from __future__ import annotations

import json
from typing import Any

from continuum.core import InvestigationState

SYSTEM_PROMPT = """You are the Continuum M8 investigation controller.

Your only job is to choose the next investigation operation from the supplied tools.
The graph is the source of truth. Continuum executes every tool call; you never invent graph facts.
Use the current InvestigationState to decide what to investigate next.

Rules:
- Choose at most one investigation tool per turn.
- Use only the supplied tools and valid arguments.
- Do not write Cypher or request arbitrary graph access.
- Do not claim an explanation is proven.
- Do not perform evidence validation, hypothesis competition, reporting, or remediation.
- If more investigation is not needed for this M8 control loop, respond with exactly DONE.
"""


def state_context(state: InvestigationState) -> str:
    payload: dict[str, Any] = {
        "question": state.question,
        "target": state.target,
        "hypotheses": [
            {
                "id": hypothesis.id,
                "description": hypothesis.description,
                "candidate_path_ids": list(hypothesis.candidate_path_ids),
                "evidence_ids": list(hypothesis.evidence_ids),
                "contradictions": list(hypothesis.contradictions),
                "gaps": list(hypothesis.gaps),
                "temporal_constraints": list(hypothesis.temporal_constraints),
            }
            for hypothesis in state.hypotheses
        ],
        "explored_nodes": sorted(state.explored_nodes),
        "explored_edges": sorted(state.explored_edges),
        "candidate_paths": [
            {
                "index": index,
                "node_ids": list(path.node_ids),
                "relationships": list(path.relationships),
                "temporal_status": path.temporal_status,
                "evidence_count": len(path.evidence),
                "missing_evidence_count": path.missing_evidence_count,
            }
            for index, path in enumerate(state.candidate_paths)
        ],
        "evidence": [item.id for item in state.evidence],
        "contradictions": list(state.contradictions),
        "gaps": list(state.gaps),
        "temporal_constraints": list(state.temporal_constraints),
        "history": [
            {
                "step": step.state_version,
                "operation": step.operation,
                "input": step.input,
                "added_nodes": list(step.added_nodes),
                "added_edges": list(step.added_edges),
                "added_paths": step.added_path_count,
                "added_evidence": step.added_evidence_count,
                "added_gaps": step.added_gap_count,
                "added_contradictions": step.added_contradiction_count,
            }
            for step in state.history
        ],
    }
    return json.dumps(payload, sort_keys=True, default=str)
