"""RevenueOS REST API ? exposes the claim pipeline over HTTP.

Tenant scoping: every request carries an X-Tenant-Id header. In production
this comes from auth; here it is explicit so the multi-tenant model is
demonstrable and the dashboard role-switcher can set it.
"""
from __future__ import annotations
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import SessionLocal
from app.db.models import (
    Tenant, Claim, Patient, Payer, ClaimCode, EligibilityCheck,
    ScrubResult, Remittance, Denial, AuditEvent,
)
from app.schemas.api import (
    TenantOut, ClaimSummary, ClaimDetail, CodeOut, ProcessResult, AnalyticsOut,
)
from app.agents.processing import process_claim

app = FastAPI(title="RevenueOS API", version="0.6.0")

# CORS so the React dashboard (Phase 7, different origin) can call this.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened at deploy
    allow_methods=["*"],
    allow_headers=["*"],
)


def _tenant_or_400(x_tenant_id: str | None) -> str:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header required")
    return x_tenant_id


@app.get("/health")
def health():
    return {"status": "ok", "service": "api"}


@app.get("/tenants", response_model=list[TenantOut])
def list_tenants():
    """Unscoped: lists tenants so the dashboard role-switcher can pick one."""
    session = SessionLocal()
    try:
        rows = session.query(Tenant).all()
        return [TenantOut(id=t.id, name=t.name, npi=t.npi) for t in rows]
    finally:
        session.close()


@app.get("/claims", response_model=list[ClaimSummary])
def list_claims(
    status: str | None = Query(None),
    limit: int = Query(100, le=500),
    x_tenant_id: str | None = Header(None),
):
    tenant_id = _tenant_or_400(x_tenant_id)
    session = SessionLocal()
    try:
        q = session.query(Claim).filter(Claim.tenant_id == tenant_id)
        if status:
            q = q.filter(Claim.status == status)
        claims = q.limit(limit).all()

        out = []
        for c in claims:
            patient = session.get(Patient, c.patient_id)
            payer = session.get(Payer, patient.payer_id) if patient else None
            out.append(ClaimSummary(
                id=c.id, tenant_id=c.tenant_id, status=c.status,
                patient_name=patient.name if patient else "",
                payer_name=payer.name if payer else "",
                total_charge=c.total_charge,
            ))
        return out
    finally:
        session.close()


@app.get("/claims/{claim_id}", response_model=ClaimDetail)
def get_claim(claim_id: str, x_tenant_id: str | None = Header(None)):
    tenant_id = _tenant_or_400(x_tenant_id)
    session = SessionLocal()
    try:
        claim = session.get(Claim, claim_id)
        if claim is None or claim.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="claim not found")

        patient = session.get(Patient, claim.patient_id)
        payer = session.get(Payer, patient.payer_id) if patient else None
        from app.db.models import Encounter
        enc = session.get(Encounter, claim.encounter_id)
        codes = session.query(ClaimCode).filter(ClaimCode.claim_id == claim.id).all()
        elig = (session.query(EligibilityCheck)
                .filter(EligibilityCheck.claim_id == claim.id).first())
        scrub = (session.query(ScrubResult)
                 .filter(ScrubResult.claim_id == claim.id)
                 .order_by(ScrubResult.created_at.desc()).first())
        remit = (session.query(Remittance)
                 .filter(Remittance.claim_id == claim.id)
                 .order_by(Remittance.created_at.desc()).first())
        denial = (session.query(Denial)
                  .filter(Denial.claim_id == claim.id)
                  .order_by(Denial.created_at.desc()).first())
        audit = (session.query(AuditEvent)
                 .filter(AuditEvent.claim_id == claim.id)
                 .order_by(AuditEvent.created_at.asc()).all())

        return ClaimDetail(
            id=claim.id, tenant_id=claim.tenant_id, status=claim.status,
            patient_name=patient.name if patient else "",
            member_id=patient.member_id if patient else "",
            payer_name=payer.name if payer else "",
            dos=enc.dos if enc else "",
            clinical_note=enc.clinical_note if enc else "",
            total_charge=claim.total_charge,
            codes=[CodeOut(code_type=c.code_type, code=c.code, modifier=c.modifier,
                           units=c.units, charge=c.charge) for c in codes],
            eligibility={"active": elig.active, "copay": elig.copay,
                         "deductible": elig.deductible} if elig else None,
            scrub={"clean": scrub.clean, "edits": scrub.edits} if scrub else None,
            remittance={"paid_amount": remit.paid_amount,
                        "allowed_amount": remit.allowed_amount,
                        "adjustments": remit.adjustments} if remit else None,
            denial={"carc_code": denial.carc_code, "reason": denial.reason,
                    "appeal_status": denial.appeal_status,
                    "appeal_letter": denial.appeal_letter} if denial else None,
            audit=[{"actor": a.actor, "action": a.action,
                    "payload": a.payload} for a in audit],
        )
    finally:
        session.close()


@app.post("/claims/{claim_id}/process", response_model=ProcessResult)
def process(claim_id: str, x_tenant_id: str | None = Header(None)):
    tenant_id = _tenant_or_400(x_tenant_id)
    try:
        result = process_claim(claim_id, tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ProcessResult(**result)


@app.get("/analytics", response_model=AnalyticsOut)
def analytics(x_tenant_id: str | None = Header(None)):
    tenant_id = _tenant_or_400(x_tenant_id)
    session = SessionLocal()
    try:
        claims = session.query(Claim).filter(Claim.tenant_id == tenant_id).all()
        total = len(claims)
        by_status: dict[str, int] = {}
        for c in claims:
            by_status[c.status] = by_status.get(c.status, 0) + 1

        claim_ids = [c.id for c in claims]
        scrubs = (session.query(ScrubResult)
                  .filter(ScrubResult.claim_id.in_(claim_ids)).all()
                  if claim_ids else [])
        clean = sum(1 for s in scrubs if s.clean)
        clean_rate = round(clean / len(scrubs), 3) if scrubs else 0.0

        denials = (session.query(Denial)
                   .filter(Denial.claim_id.in_(claim_ids)).all()
                   if claim_ids else [])
        adjudicated = by_status.get("PAID", 0) + by_status.get("DENIED", 0) \
            + by_status.get("APPEAL_DRAFTED", 0)
        denial_rate = round(len(denials) / adjudicated, 3) if adjudicated else 0.0

        remits = (session.query(Remittance)
                  .filter(Remittance.claim_id.in_(claim_ids)).all()
                  if claim_ids else [])
        total_paid = round(sum(r.paid_amount for r in remits), 2)
        total_billed = round(sum(c.total_charge for c in claims), 2)

        denial_reasons: dict[str, int] = {}
        for d in denials:
            denial_reasons[d.carc_code] = denial_reasons.get(d.carc_code, 0) + 1

        return AnalyticsOut(
            tenant_id=tenant_id, total_claims=total, by_status=by_status,
            clean_claim_rate=clean_rate, denial_rate=denial_rate,
            total_paid=total_paid, total_billed=total_billed,
            denial_reasons=denial_reasons,
        )
    finally:
        session.close()
