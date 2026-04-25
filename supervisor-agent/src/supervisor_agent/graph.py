"""LangGraph state-machine for the paper-generation pipeline.

Graph topology:
    Planner → Researcher → Writer → Reviewer
                              ↑          ↓
                              └── (fail, revision < 2)

Two entry points exposed:
    build_outline_graph()  — Planner only (for outline preview)
    build_full_graph()     — Full pipeline (after user confirms outline)
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from supervisor_agent.state import PaperState
from supervisor_agent.nodes import (
    planner_node,
    revise_outline_node,
    researcher_node,
    writer_node,
    reviewer_node,
)

logger = logging.getLogger(__name__)

MAX_REVISIONS = 2


# ── Conditional edge: review pass or loop back ──

def _should_revise(state: dict) -> str:
    """Return next node name based on review result."""
    if state.get("review_pass", False):
        return "end"

    # 👇 必须动态读取状态里的数字，绝不能用写死的 MAX_REVISIONS！
    max_rev = state.get("max_revisions", 2) 

    if state.get("revision_count", 0) >= max_rev:
        logger.warning(f"Max revisions ({max_rev}) reached — finishing anyway.")
        return "end"
    
    return "writer"



# ── Graph builders ──

def build_outline_graph() -> StateGraph:
    """Build a minimal graph that only runs the Planner node.

    Used by the /api/generate_outline endpoint so the user can
    preview and confirm the outline before committing to full generation.
    """
    g = StateGraph(PaperState)
    g.add_node("planner", planner_node)
    g.set_entry_point("planner")
    g.add_edge("planner", END)
    return g.compile()


def build_full_graph():
    """Full pipeline: Researcher → Writer → Reviewer (with revision loop).

    Expects state to already contain outline / sections from the Planner
    (i.e. the user confirmed the outline produced by build_outline_graph).
    """
    g = StateGraph(PaperState)

    g.add_node("researcher", researcher_node)
    g.add_node("writer", writer_node)
    g.add_node("reviewer", reviewer_node)

    g.set_entry_point("researcher")
    g.add_edge("researcher", "writer")
    g.add_edge("writer", "reviewer")

    g.add_conditional_edges(
        "reviewer",
        _should_revise,
        {"writer": "writer", "end": END},
    )

    return g.compile()


def build_revise_graph():
    """Minimal graph: revise an existing outline based on user feedback."""
    g = StateGraph(PaperState)
    g.add_node("revise", revise_outline_node)
    g.set_entry_point("revise")
    g.add_edge("revise", END)
    return g.compile()
