"""Mock payer service ? simulates 835/ERA adjudication.

Applies realistic payer logic:
- Clean claims: paid, with a contractual adjustment (CO-45) and the
  patient responsibility (copay/deductible) carved out.
- Flawed claims: denied with the CARC/RARC that matches the actual defect,
  using the same denials.yaml the generator uses for consistency.

Defects are inferred from the claim itself (missing modifier on a
modifier-required CPT, dx/cpt mismatch) plus an eligibility flag passed in.
"""
from __future__ import annotations
from pathlib import Path

import yaml
from fastapi import FastAPI

from app.schemas.edi import ClaimSubmission, RemittanceAdvice, Adjustment

app = FastAPI(title="Mock Payer Service (835/ERA)")

PATTERNS = Path(__file__).resolve().parents[3] / "synthetic" / "patterns"


def _load_denials() -> dict[str, dict]:
    with open(PATTERNS / "denials.yaml", "r", encoding="utf-8") as f:
        rows = yaml.safe_load(f)["denials"]
    # Index by the defect that triggers them.
    return {r["defect_trigger"]: r for r in rows}


def _load_procedures() -> dict[str, dict]:
    with open(PATTERNS / "procedures.yaml", "r", encoding="utf-8") as f:
        rows = yaml.safe_load(f)["procedures"]
    return {r["cpt"]: r for r in rows}


DENIALS_BY_DEFECT = _load_denials()
PROCEDURES = _load_procedures()


@app.get("/health")
def health():
    return {"status": "ok", "service": "payer"}


def _detect_defect(claim: ClaimSubmission, eligibility_active: bool) -> str:
    if not eligibility_active:
        return "inactive_eligibility"

    cpt_lines = [c for c in claim.codes if c.code_type == "cpt"]
    icd_lines = [c for c in claim.codes if c.code_type == "icd10"]
    dx_codes = {c.code for c in icd_lines}

    for cpt in cpt_lines:
        proc = PROCEDURES.get(cpt.code)
        if not proc:
            continue
        # Missing required modifier?
        if proc.get("requires_modifier") and not cpt.modifier:
            return "missing_modifier"
        # Diagnosis not in the valid set for this procedure?
        valid = set(proc.get("valid_dx", []))
        if valid and dx_codes and not (dx_codes & valid):
            return "dx_cpt_mismatch"

    return "none"


@app.post("/adjudicate", response_model=RemittanceAdvice)
def adjudicate(
    claim: ClaimSubmission,
    eligibility_active: bool = True,
    patient_responsibility: float = 0.0,
) -> RemittanceAdvice:
    defect = _detect_defect(claim, eligibility_active)
    billed = claim.total_charge

    # A denial exists for this defect and it is a true denial (not CO-45/PR-1,
    # which are adjustments on otherwise-paid claims).
    denial = DENIALS_BY_DEFECT.get(defect)
    is_denial = defect != "none" and denial is not None

    if is_denial:
        return RemittanceAdvice(
            claim_id=claim.claim_id,
            status="DENIED",
            billed_amount=billed,
            allowed_amount=0.0,
            paid_amount=0.0,
            patient_responsibility=0.0,
            carc_code=denial["carc"],
            rarc_code=denial["rarc"] or None,
            denial_reason=denial["reason"],
            adjustments=[
                Adjustment(
                    group_code=denial["carc"].split("-")[0],
                    reason_code=denial["carc"],
                    amount=billed,
                )
            ],
            raw_835={"defect": defect, "outcome": "denied"},
        )

    # Clean claim: pay it. Contractual adjustment ~30% (CO-45), then carve
    # out patient responsibility (copay/deductible).
    allowed = round(billed * 0.70, 2)
    pr = min(patient_responsibility, allowed)
    paid = round(allowed - pr, 2)
    contractual = round(billed - allowed, 2)

    return RemittanceAdvice(
        claim_id=claim.claim_id,
        status="PAID",
        billed_amount=billed,
        allowed_amount=allowed,
        paid_amount=paid,
        patient_responsibility=pr,
        adjustments=[
            Adjustment(group_code="CO", reason_code="CO-45", amount=contractual)
        ],
        raw_835={"defect": "none", "outcome": "paid"},
    )
