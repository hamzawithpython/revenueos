"""Supervisor ? the LangGraph StateGraph that routes a claim through the
agent pipeline. Phase 3 wires the first two stages: eligibility then coding.

We use ClaimState (a Pydantic model) directly as the graph state. Each
node is a function ClaimState -> ClaimState. LangGraph threads the model
through as the channel value, so nodes work with typed attributes rather
than dict subscripting.

Node names must NOT collide with ClaimState field names (LangGraph treats
field names as reserved state keys), hence the _node-suffixed names.
"""
from __future__ import annotations
from langgraph.graph import StateGraph, START, END

from app.agents.state import ClaimState
from app.agents.eligibility_agent import run_eligibility
from app.agents.coding_agent import run_coding


def _eligibility_node(state: ClaimState) -> ClaimState:
    return run_eligibility(state)


def _coding_node(state: ClaimState) -> ClaimState:
    return run_coding(state)


def build_supervisor():
    """Construct and compile the claim-processing graph.

    Phase 3 flow:  START -> eligibility_check -> coding_assign -> END
    Later phases insert scrubber, submission, adjudication, denial.
    """
    graph = StateGraph(ClaimState)

    graph.add_node("eligibility_check", _eligibility_node)
    graph.add_node("coding_assign", _coding_node)

    graph.add_edge(START, "eligibility_check")
    graph.add_edge("eligibility_check", "coding_assign")
    graph.add_edge("coding_assign", END)

    return graph.compile()


supervisor = build_supervisor()
