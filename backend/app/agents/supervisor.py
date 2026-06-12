"""Supervisor ? LangGraph StateGraph with conditional routing and the
denial -> correct -> resubmit loop.

Phase 5 flow:
  START -> eligibility_check -> coding_assign -> scrub_check -> adjudicate
  adjudicate --(PAID)--> END
  adjudicate --(DENIED)--> denial_mgmt
  denial_mgmt --(correct_resubmit, attempts<2)--> adjudicate   [the loop]
  denial_mgmt --(appeal / write_off / max attempts)--> END

Node names must not collide with ClaimState field names.
"""
from __future__ import annotations
from langgraph.graph import StateGraph, START, END

from app.agents.state import ClaimState
from app.agents.eligibility_agent import run_eligibility
from app.agents.coding_agent import run_coding
from app.agents.scrubber_agent import run_scrubber
from app.agents.adjudication_agent import run_adjudication
from app.agents.denial_agent import run_denial_management

MAX_RESUBMIT_ATTEMPTS = 2


def _eligibility_node(state: ClaimState) -> ClaimState:
    return run_eligibility(state)


def _coding_node(state: ClaimState) -> ClaimState:
    return run_coding(state)


def _scrub_node(state: ClaimState) -> ClaimState:
    return run_scrubber(state)


def _adjudicate_node(state: ClaimState) -> ClaimState:
    return run_adjudication(state)


def _denial_node(state: ClaimState) -> ClaimState:
    return run_denial_management(state)


def _route_after_adjudication(state: ClaimState) -> str:
    """PAID (or clearinghouse-rejected/error) ends; DENIED goes to denial mgmt."""
    if state.adjudication.outcome == "DENIED":
        return "denial_handle"
    return END


def _route_after_denial(state: ClaimState) -> str:
    """Correctable denials loop back to adjudication (capped); others end."""
    if (state.denial_mgmt.strategy == "correct_resubmit"
            and state.denial_mgmt.attempts < MAX_RESUBMIT_ATTEMPTS):
        state.denial_mgmt.resubmitted = True
        return "adjudicate"
    return END


def build_supervisor():
    graph = StateGraph(ClaimState)

    graph.add_node("eligibility_check", _eligibility_node)
    graph.add_node("coding_assign", _coding_node)
    graph.add_node("scrub_check", _scrub_node)
    graph.add_node("adjudicate", _adjudicate_node)
    graph.add_node("denial_handle", _denial_node)

    graph.add_edge(START, "eligibility_check")
    graph.add_edge("eligibility_check", "coding_assign")
    graph.add_edge("coding_assign", "scrub_check")
    graph.add_edge("scrub_check", "adjudicate")

    graph.add_conditional_edges(
        "adjudicate", _route_after_adjudication,
        {"denial_handle": "denial_handle", END: END},
    )
    graph.add_conditional_edges(
        "denial_handle", _route_after_denial,
        {"adjudicate": "adjudicate", END: END},
    )

    return graph.compile()


supervisor = build_supervisor()

