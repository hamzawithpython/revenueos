"""Mock eligibility service ? simulates a 270/271 transaction.

Deterministic by member_id so the same patient always gets the same
coverage answer within a run, but ~12% of members come back inactive
to exercise the downstream eligibility-failure path.
"""
from __future__ import annotations
import hashlib

from fastapi import FastAPI

from app.schemas.edi import EligibilityRequest, EligibilityResponse

app = FastAPI(title="Mock Eligibility Service (270/271)")


def _hash_pct(seed: str) -> float:
    """Stable 0..1 value from a string, for deterministic branching."""
    h = hashlib.sha256(seed.encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


@app.get("/health")
def health():
    return {"status": "ok", "service": "eligibility"}


@app.post("/eligibility", response_model=EligibilityResponse)
def check_eligibility(req: EligibilityRequest) -> EligibilityResponse:
    roll = _hash_pct(req.member_id)
    active = roll > 0.12  # ~12% inactive

    if not active:
        return EligibilityResponse(
            active=False,
            plan_name=f"{req.payer_name} (terminated)",
            raw_271={"coverage": "inactive", "member_id": req.member_id},
        )

    # Derive plausible benefit amounts deterministically.
    copay = round(10 + _hash_pct(req.member_id + "copay") * 40, 2)  # 10..50
    deductible = round(_hash_pct(req.member_id + "ded") * 2000, 2)  # 0..2000
    deductible_met = _hash_pct(req.member_id + "met") > 0.5

    return EligibilityResponse(
        active=True,
        copay=copay,
        deductible=deductible,
        deductible_met=deductible_met,
        plan_name=f"{req.payer_name} PPO",
        raw_271={
            "coverage": "active",
            "member_id": req.member_id,
            "copay": copay,
            "deductible": deductible,
            "deductible_met": deductible_met,
        },
    )
