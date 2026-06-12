"""ClaimState ? the object threaded through the LangGraph supervisor.

Every agent node receives this, mutates its slice, and returns it. The
claim_id anchors it to the DB row; agents persist their results and also
reflect them here so downstream nodes can read without a round-trip.
"""
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field

ClaimStatus = Literal[
    "DRAFT", "ELIGIBILITY_CHECKED", "CODED", "SCRUBBED",
    "SUBMITTED", "ADJUDICATED", "PAID", "DENIED",
    "APPEAL_DRAFTED", "RESUBMITTED",
]


class CodeEntry(BaseModel):
    code_type: str  # icd10 / cpt
    code: str
    modifier: Optional[str] = None
    units: int = 1
    charge: float = 0.0


class EligibilitySlice(BaseModel):
    checked: bool = False
    active: bool = False
    copay: float = 0.0
    deductible: float = 0.0
    deductible_met: bool = False
    plan_name: str = ""


class CodingSlice(BaseModel):
    coded: bool = False
    codes: list[CodeEntry] = Field(default_factory=list)
    rationale: str = ""


class ScrubSlice(BaseModel):
    scrubbed: bool = False
    clean: bool = False
    edits: list[str] = Field(default_factory=list)


class AdjudicationSlice(BaseModel):
    submitted: bool = False
    accepted_by_clearinghouse: bool = False
    front_end_edits: list[str] = Field(default_factory=list)
    adjudicated: bool = False
    outcome: str = ""  # PAID / DENIED / ""
    billed_amount: float = 0.0
    allowed_amount: float = 0.0
    paid_amount: float = 0.0
    patient_responsibility: float = 0.0
    carc_code: Optional[str] = None
    rarc_code: Optional[str] = None
    denial_reason: Optional[str] = None


class DenialMgmtSlice(BaseModel):
    handled: bool = False
    strategy: str = ""  # "correct_resubmit" / "appeal" / "write_off"
    correction_applied: str = ""
    appeal_letter: str = ""
    resubmitted: bool = False
    resolved_outcome: str = ""  # outcome after resubmission, if any
    attempts: int = 0


class ClaimState(BaseModel):
    # Identity / tenancy
    claim_id: str
    tenant_id: str

    # Lifecycle
    status: ClaimStatus = "DRAFT"

    # Inputs the agents read
    member_id: str
    payer_name: str
    patient_name: str
    dob: str
    dos: str
    pos: str
    provider_npi: str
    clinical_note: str
    total_charge: float = 0.0

    # Agent outputs
    eligibility: EligibilitySlice = Field(default_factory=EligibilitySlice)
    coding: CodingSlice = Field(default_factory=CodingSlice)
    scrub: ScrubSlice = Field(default_factory=ScrubSlice)
    adjudication: AdjudicationSlice = Field(default_factory=AdjudicationSlice)
    denial_mgmt: DenialMgmtSlice = Field(default_factory=DenialMgmtSlice)

    # Routing / control
    needs_human_review: bool = False
    errors: list[str] = Field(default_factory=list)

    model_config = {"validate_assignment": True}


