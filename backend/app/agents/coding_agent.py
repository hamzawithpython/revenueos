"""Coding agent ? uses Groq to assign/validate ICD-10 and CPT codes
against the clinical note, constrained to the known code set.

The LLM reasons about whether the draft codes match the documented
encounter and returns structured JSON. We constrain it to the catalogue
loaded from the pattern files so it cannot invent codes ? a real coding
agent would use an official code set; here the synthetic catalogue stands
in for that.
"""
from __future__ import annotations
from pathlib import Path
import yaml

from app.agents.state import ClaimState, CodeEntry
from app.agents.llm import chat_json
from app.db.session import SessionLocal
from app.db.models import ClaimCode, AuditEvent

PATTERNS = Path(__file__).resolve().parents[2] / "synthetic" / "patterns"


def _load_catalogue() -> tuple[list[dict], list[dict]]:
    with open(PATTERNS / "procedures.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["procedures"], data["diagnoses"]


PROCEDURES, DIAGNOSES = _load_catalogue()

_CPT_LIST = ", ".join(f"{p['cpt']} ({p['description']})" for p in PROCEDURES)
_ICD_LIST = ", ".join(f"{d['icd10']} ({d['description']})" for d in DIAGNOSES)

SYSTEM = f"""You are a medical coding assistant. Given a clinical note and
draft codes, validate and finalize the ICD-10 diagnosis and CPT procedure
codes for the claim.

You MUST only use codes from these catalogues.
CPT procedures: {_CPT_LIST}
ICD-10 diagnoses: {_ICD_LIST}

Return JSON with this exact shape:
{{
  "cpt": [{{"code": "99213", "modifier": null}}],
  "icd10": ["I10"],
  "rationale": "one sentence explaining the coding decision"
}}
Only include codes justified by the note. Keep the existing CPT if it is
appropriate. Do not invent codes outside the catalogues."""


def run_coding(state: ClaimState) -> ClaimState:
    draft_cpt = [c.code for c in state.coding.codes if c.code_type == "cpt"]
    draft_icd = [c.code for c in state.coding.codes if c.code_type == "icd10"]

    user = (
        f"Clinical note: {state.clinical_note}\n"
        f"Draft CPT codes: {draft_cpt or 'none'}\n"
        f"Draft ICD-10 codes: {draft_icd or 'none'}\n"
        f"Charge on claim: {state.total_charge}"
    )

    try:
        result = chat_json(SYSTEM, user)
    except Exception as exc:
        state.errors.append(f"coding_llm_error: {exc}")
        state.needs_human_review = True
        return state

    # Build the finalized code list, charges carried from the catalogue.
    charge_by_cpt = {p["cpt"]: p["charge"] for p in PROCEDURES}
    new_codes: list[CodeEntry] = []
    for item in result.get("cpt", []):
        code = item.get("code")
        if code in charge_by_cpt:
            new_codes.append(CodeEntry(
                code_type="cpt", code=code,
                modifier=item.get("modifier"),
                units=1, charge=charge_by_cpt[code],
            ))
    valid_icd = {d["icd10"] for d in DIAGNOSES}
    for code in result.get("icd10", []):
        if code in valid_icd:
            new_codes.append(CodeEntry(code_type="icd10", code=code))

    state.coding.coded = True
    state.coding.codes = new_codes
    state.coding.rationale = result.get("rationale", "")
    state.total_charge = sum(c.charge for c in new_codes if c.code_type == "cpt")

    # Persist: replace this claim's codes with the finalized set.
    session = SessionLocal()
    try:
        session.query(ClaimCode).filter(ClaimCode.claim_id == state.claim_id).delete()
        for c in new_codes:
            session.add(ClaimCode(
                claim_id=state.claim_id, code_type=c.code_type, code=c.code,
                modifier=c.modifier, units=c.units, charge=c.charge,
            ))
        session.add(AuditEvent(
            tenant_id=state.tenant_id, claim_id=state.claim_id,
            actor="coding_agent", action="claim_coded",
            payload={"cpt": [c.code for c in new_codes if c.code_type == "cpt"],
                     "icd10": [c.code for c in new_codes if c.code_type == "icd10"],
                     "rationale": state.coding.rationale},
        ))
        session.commit()
    finally:
        session.close()

    state.status = "CODED"
    return state
