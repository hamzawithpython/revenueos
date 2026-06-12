"""Supervisor ? the LangGraph StateGraph that routes a claim through the
agent pipeline.

We use ClaimState (a Pydantic model) directly as the graph state. Each
node is a function ClaimState -> ClaimState. Node names must NOT collide
with ClaimState field names (LangGraph treats field names as reserved
state keys), hence the suffixed names.

Phase 4 flow:
  START -> eligibility_check -> coding_assign -> scrub_check
        -> adjudicate -> END
"""
from __future__ import annotations
from langgraph.graph import StateGraph, START, END

from app.agents.state import ClaimState
from app.agents.eligibility_agent import run_eligibility
from app.agents.coding_agent import run_coding
from app.agents.scrubber_agent import run_scrubber
from app.agents.adjudication_agent import run_adjudication


def _eligibility_node(state: ClaimState) -> ClaimState:
    return run_eligibility(state)


def _coding_node(state: ClaimState) -> ClaimState:
    return run_coding(state)


def _scrub_node(state: ClaimState) -> ClaimState:
    return run_scrubber(state)


def _adjudicate_node(state: ClaimState) -> ClaimState:
    return run_adjudication(state)


def build_supervisor():
    """Construct and compile the claim-processing graph."""
    graph = StateGraph(ClaimState)

    graph.add_node("eligibility_check", _eligibility_node)
    graph.add_node("coding_assign", _coding_node)
    graph.add_node("scrub_check", _scrub_node)
    graph.add_node("adjudicate", _adjudicate_node)

    graph.add_edge(START, "eligibility_check")
    graph.add_edge("eligibility_check", "coding_assign")
    graph.add_edge("coding_assign", "scrub_check")
    graph.add_edge("scrub_check", "adjudicate")
    graph.add_edge("adjudicate", END)

    return graph.compile()


supervisor = build_supervisor()
