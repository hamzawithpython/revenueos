"""Claim processing service ? loads a claim, runs it through the supervisor
graph, persists the final status. Shared by the API and the CLI runner.
"""
from __future__ import annotations

from app.db.session import SessionLocal
from app.db.models import Claim, Encounter, Patient, ClaimCode, Payer
from app.agents.state import ClaimState, CodeEntry
from app.agents.supervisor import supervisor


def _load_state(session, claim: Claim) -> ClaimState:
    enc = session.get(Encounter, claim.encounter_id)
    patient = session.get(Patient, claim.patient_id)
    payer = session.get(Payer, patient.payer_id)
    codes = session.query(ClaimCode).filter(ClaimCode.claim_id == claim.id).all()

    return ClaimState(
        claim_id=claim.id,
        tenant_id=claim.tenant_id,
        status=claim.status,
        member_id=patient.member_id,
        payer_name=payer.name if payer else "Unknown",
        patient_name=patient.name,
        dob=patient.dob,
        dos=enc.dos,
        pos=enc.pos,
        provider_npi=enc.provider_npi,
        clinical_note=enc.clinical_note,
        total_charge=claim.total_charge,
        coding={"coded": False,
                "codes": [CodeEntry(
                    code_type=c.code_type, code=c.code, modifier=c.modifier,
                    units=c.units, charge=c.charge) for c in codes],
                "rationale": ""},
    )


def process_claim(claim_id: str, tenant_id: str) -> dict:
    """Run a single claim through the full pipeline. Tenant-scoped:
    refuses to process a claim that does not belong to the tenant."""
    session = SessionLocal()
    try:
        claim = session.get(Claim, claim_id)
        if claim is None or claim.tenant_id != tenant_id:
            raise ValueError("claim not found for tenant")

        start_status = claim.status
        state = _load_state(session, claim)
        final = supervisor.invoke(state)
        final_state = final if isinstance(final, ClaimState) else ClaimState(**final)

        claim.status = final_state.status
        session.commit()

        return {
            "claim_id": claim_id,
            "start_status": start_status,
            "end_status": final_state.status,
            "outcome": final_state.adjudication.outcome or final_state.status,
            "needs_human_review": final_state.needs_human_review,
        }
    finally:
        session.close()
