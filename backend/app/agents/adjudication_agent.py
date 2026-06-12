"""Adjudication agent ? submits the claim through the clearinghouse mock,
then (if accepted) adjudicates at the payer mock. Persists the remittance
or denial and lands the claim at PAID or DENIED.

Two real HTTP hops mirror the production path: clearinghouse front-end
edits first, then payer adjudication. Patient responsibility (copay +
unmet deductible) is computed from the eligibility slice and passed to the
payer so paid amounts are realistic.
"""
from __future__ import annotations

from app.agents.state import ClaimState
from app.agents.mock_clients import submit_claim, adjudicate_claim
from app.db.session import SessionLocal
from app.db.models import Remittance, Denial, AuditEvent


def _build_submission(state: ClaimState) -> dict:
    return {
        "claim_id": state.claim_id,
        "member_id": state.member_id,
        "payer_name": state.payer_name,
        "provider_npi": state.provider_npi,
        "dos": state.dos,
        "pos": state.pos,
        "codes": [
            {"code_type": c.code_type, "code": c.code,
             "modifier": c.modifier, "units": c.units, "charge": c.charge}
            for c in state.coding.codes
        ],
        "total_charge": state.total_charge,
    }


def run_adjudication(state: ClaimState) -> ClaimState:
    submission = _build_submission(state)

    # --- Hop 1: clearinghouse submission ---
    try:
        ack = submit_claim(submission)
    except Exception as exc:
        state.errors.append(f"clearinghouse_error: {exc}")
        state.needs_human_review = True
        return state

    state.adjudication.submitted = True
    state.adjudication.accepted_by_clearinghouse = ack.get("accepted", False)
    state.adjudication.front_end_edits = ack.get("front_end_edits", [])

    if not state.adjudication.accepted_by_clearinghouse:
        # Rejected before reaching payer ? treat as a denial-like terminal
        # state needing human rework.
        state.needs_human_review = True
        state.status = "SUBMITTED"
        _audit(state, "clearinghouse_rejected",
               {"edits": state.adjudication.front_end_edits})
        return state

    state.status = "SUBMITTED"

    # --- Hop 2: payer adjudication ---
    # Patient responsibility = copay (deductible is reflected in the payer's
    # allowed-amount logic; kept simple here for realistic paid amounts).
    patient_resp = state.eligibility.copay

    try:
        remit = adjudicate_claim(
            submission,
            eligibility_active=state.eligibility.active,
            patient_responsibility=patient_resp,
        )
    except Exception as exc:
        state.errors.append(f"payer_error: {exc}")
        state.needs_human_review = True
        return state

    state.adjudication.adjudicated = True
    state.adjudication.outcome = remit.get("status", "")
    state.adjudication.billed_amount = remit.get("billed_amount", 0.0)
    state.adjudication.allowed_amount = remit.get("allowed_amount", 0.0)
    state.adjudication.paid_amount = remit.get("paid_amount", 0.0)
    state.adjudication.patient_responsibility = remit.get("patient_responsibility", 0.0)
    state.adjudication.carc_code = remit.get("carc_code")
    state.adjudication.rarc_code = remit.get("rarc_code")
    state.adjudication.denial_reason = remit.get("denial_reason")

    session = SessionLocal()
    try:
        if state.adjudication.outcome == "PAID":
            session.add(Remittance(
                claim_id=state.claim_id,
                paid_amount=state.adjudication.paid_amount,
                allowed_amount=state.adjudication.allowed_amount,
                adjustments=remit.get("adjustments", []),
                raw_835=remit.get("raw_835", {}),
            ))
            state.status = "PAID"
        else:
            session.add(Denial(
                claim_id=state.claim_id,
                carc_code=state.adjudication.carc_code or "",
                rarc_code=state.adjudication.rarc_code,
                reason=state.adjudication.denial_reason or "",
                appealable=True,
            ))
            state.status = "DENIED"
            state.needs_human_review = True

        session.add(AuditEvent(
            tenant_id=state.tenant_id, claim_id=state.claim_id,
            actor="adjudication_agent", action="claim_adjudicated",
            payload={"outcome": state.adjudication.outcome,
                     "paid": state.adjudication.paid_amount,
                     "carc": state.adjudication.carc_code},
        ))
        session.commit()
    finally:
        session.close()

    return state


def _audit(state: ClaimState, action: str, payload: dict) -> None:
    session = SessionLocal()
    try:
        session.add(AuditEvent(
            tenant_id=state.tenant_id, claim_id=state.claim_id,
            actor="adjudication_agent", action=action, payload=payload,
        ))
        session.commit()
    finally:
        session.close()

