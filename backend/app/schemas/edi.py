"""Shared EDI-shaped request/response schemas for the mock payer ecosystem.

These mirror the real-world transactions so the integration boundary is
honest: swapping a mock for Availity/Change Healthcare is a config change,
not a schema rewrite.

SYNTHETIC DATA ONLY.
"""
from __future__ import annotations
from pydantic import BaseModel, Field


# --- 270/271 Eligibility ---
class EligibilityRequest(BaseModel):
    """Mirrors a 270 eligibility inquiry."""
    member_id: str
    payer_name: str
    patient_name: str
    dob: str
    dos: str  # date of service


class EligibilityResponse(BaseModel):
    """Mirrors a 271 eligibility response."""
    active: bool
    copay: float = 0.0
    deductible: float = 0.0
    deductible_met: bool = False
    plan_name: str = ""
    raw_271: dict = Field(default_factory=dict)


# --- 837 Claim Submission ---
class ClaimCodeDTO(BaseModel):
    code_type: str  # icd10 / cpt
    code: str
    modifier: str | None = None
    units: int = 1
    charge: float = 0.0


class ClaimSubmission(BaseModel):
    """Mirrors an 837 professional claim."""
    claim_id: str
    member_id: str
    payer_name: str
    provider_npi: str
    dos: str
    pos: str
    codes: list[ClaimCodeDTO]
    total_charge: float


class SubmissionAck(BaseModel):
    """Mirrors a 999/277CA acknowledgement from a clearinghouse."""
    accepted: bool
    trace_number: str
    front_end_edits: list[str] = Field(default_factory=list)


# --- 835/ERA Adjudication ---
class Adjustment(BaseModel):
    group_code: str  # CO, PR, OA, etc.
    reason_code: str  # CARC
    amount: float


class RemittanceAdvice(BaseModel):
    """Mirrors an 835 electronic remittance advice."""
    claim_id: str
    status: str  # PAID / DENIED
    billed_amount: float
    allowed_amount: float
    paid_amount: float
    patient_responsibility: float = 0.0
    adjustments: list[Adjustment] = Field(default_factory=list)
    carc_code: str | None = None
    rarc_code: str | None = None
    denial_reason: str | None = None
    raw_835: dict = Field(default_factory=dict)
