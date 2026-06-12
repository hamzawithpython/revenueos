"""API response schemas (DTOs). Separate from ORM models so the API
contract is stable and explicit.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class TenantOut(BaseModel):
    id: str
    name: str
    npi: Optional[str] = None


class CodeOut(BaseModel):
    code_type: str
    code: str
    modifier: Optional[str] = None
    units: int = 1
    charge: float = 0.0


class ClaimSummary(BaseModel):
    id: str
    tenant_id: str
    status: str
    patient_name: str
    payer_name: str
    total_charge: float


class ClaimDetail(BaseModel):
    id: str
    tenant_id: str
    status: str
    patient_name: str
    member_id: str
    payer_name: str
    dos: str
    clinical_note: str
    total_charge: float
    codes: list[CodeOut] = []
    eligibility: Optional[dict] = None
    scrub: Optional[dict] = None
    remittance: Optional[dict] = None
    denial: Optional[dict] = None
    audit: list[dict] = []


class ProcessResult(BaseModel):
    claim_id: str
    start_status: str
    end_status: str
    outcome: str
    needs_human_review: bool


class AnalyticsOut(BaseModel):
    tenant_id: str
    total_claims: int
    by_status: dict
    clean_claim_rate: float
    denial_rate: float
    total_paid: float
    total_billed: float
    denial_reasons: dict
