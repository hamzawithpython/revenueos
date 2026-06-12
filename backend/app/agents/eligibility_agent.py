"""Eligibility agent ? calls the mock 270/271 service, persists the
result, and updates ClaimState.

This agent is deterministic (no LLM): eligibility is a data lookup, not
a reasoning task. It hits the mock service exactly as it would hit a real
payer's eligibility endpoint.
"""
from __future__ import annotations

from app.agents.state import ClaimState
from app.agents.mock_clients import check_eligibility
from app.db.session import SessionLocal
from app.db.models import EligibilityCheck, AuditEvent


def run_eligibility(state: ClaimState) -> ClaimState:
    payload = {
        "member_id": state.member_id,
        "payer_name": state.payer_name,
        "patient_name": state.patient_name,
        "dob": state.dob,
        "dos": state.dos,
    }

    try:
        result = check_eligibility(payload)
    except Exception as exc:  # transport / service down
        state.errors.append(f"eligibility_service_error: {exc}")
        state.needs_human_review = True
        return state

    # Reflect into state
    state.eligibility.checked = True
    state.eligibility.active = result.get("active", False)
    state.eligibility.copay = result.get("copay", 0.0)
    state.eligibility.deductible = result.get("deductible", 0.0)
    state.eligibility.deductible_met = result.get("deductible_met", False)
    state.eligibility.plan_name = result.get("plan_name", "")

    # Persist the 271 and an audit event
    session = SessionLocal()
    try:
        session.add(EligibilityCheck(
            claim_id=state.claim_id,
            active=state.eligibility.active,
            copay=state.eligibility.copay,
            deductible=state.eligibility.deductible,
            raw_271=result.get("raw_271", {}),
        ))
        session.add(AuditEvent(
            tenant_id=state.tenant_id,
            claim_id=state.claim_id,
            actor="eligibility_agent",
            action="eligibility_checked",
            payload={"active": state.eligibility.active,
                     "plan": state.eligibility.plan_name},
        ))
        session.commit()
    finally:
        session.close()

    # Inactive coverage is a human-review trigger but not a hard stop;
    # the pipeline continues so the denial path can be exercised later.
    if not state.eligibility.active:
        state.needs_human_review = True

    state.status = "ELIGIBILITY_CHECKED"
    return state
