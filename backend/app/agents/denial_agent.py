"""Denial-management agent ? reads a denied claim, decides a recovery
strategy from the CARC code, and either corrects+resubmits or drafts a
grounded appeal letter.

Strategy mapping:
- CO-16 (missing info / modifier)  -> correct_resubmit: add the required modifier
- CO-11 (dx/cpt mismatch)          -> correct_resubmit: align dx to a valid one
- CO-27 (coverage terminated)      -> appeal: draft an appeal letter
- CO-97 (bundled)                  -> appeal: draft an appeal letter
- CO-45 / PR-1 (contractual/ded.)  -> write_off: not appealable

Corrections are applied to the in-state codes so the resubmission carries
the fix. The LLM is used only for appeal-letter prose, grounded in the
actual denial reason ? not for the correction decision (that's rule-based).
"""
from __future__ import annotations
from pathlib import Path
import yaml

from app.agents.state import ClaimState
from app.agents.llm import chat_text
from app.db.session import SessionLocal
from app.db.models import Denial, ClaimCode, AuditEvent

PATTERNS = Path(__file__).resolve().parents[2] / "synthetic" / "patterns"


def _load_procedures() -> dict[str, dict]:
    with open(PATTERNS / "procedures.yaml", "r", encoding="utf-8") as f:
        rows = yaml.safe_load(f)["procedures"]
    return {r["cpt"]: r for r in rows}


PROCEDURES = _load_procedures()

CORRECTABLE = {"CO-16", "CO-11"}
APPEALABLE = {"CO-27", "CO-97"}
WRITE_OFF = {"CO-45", "PR-1"}

APPEAL_SYSTEM = """You are a medical billing appeals specialist. Draft a
concise, professional appeal letter (120-180 words) contesting a claim
denial. Ground the letter in the specific denial reason provided. State
the claim is being appealed, give a brief medical-necessity / coverage
rationale appropriate to the denial reason, and request reprocessing.
Do not invent patient-specific clinical details beyond what is provided.
Return only the letter body."""


def _apply_correction(state: ClaimState) -> str:
    """Mutate state.coding.codes to fix the flagged defect. Returns a
    human-readable description of what was changed."""
    carc = state.adjudication.carc_code

    if carc == "CO-16":
        # Missing modifier: add LT to the first modifier-requiring CPT.
        for c in state.coding.codes:
            if c.code_type == "cpt":
                proc = PROCEDURES.get(c.code)
                if proc and proc.get("requires_modifier") and not c.modifier:
                    c.modifier = "LT"
                    return f"Added modifier LT to CPT {c.code}"
        return "No missing modifier found to correct"

    if carc == "CO-11":
        # dx/cpt mismatch: replace dx codes with a valid one for the CPT.
        cpt = next((c for c in state.coding.codes if c.code_type == "cpt"), None)
        if cpt:
            proc = PROCEDURES.get(cpt.code)
            valid = proc.get("valid_dx", []) if proc else []
            if valid:
                # Drop existing icd codes, add the first valid dx.
                state.coding.codes = [
                    c for c in state.coding.codes if c.code_type != "icd10"
                ]
                from app.agents.state import CodeEntry
                state.coding.codes.append(CodeEntry(code_type="icd10", code=valid[0]))
                return f"Realigned diagnosis to {valid[0]} (valid for CPT {cpt.code})"
        return "Could not realign diagnosis"

    return "No correction rule for this denial"


def run_denial_management(state: ClaimState) -> ClaimState:
    carc = state.adjudication.carc_code or ""
    state.denial_mgmt.attempts += 1

    if carc in CORRECTABLE:
        state.denial_mgmt.strategy = "correct_resubmit"
        state.denial_mgmt.correction_applied = _apply_correction(state)
    elif carc in APPEALABLE:
        state.denial_mgmt.strategy = "appeal"
        user = (
            f"Denial code: {carc}\n"
            f"Denial reason: {state.adjudication.denial_reason}\n"
            f"Payer: {state.payer_name}\n"
            f"Procedure(s): {[c.code for c in state.coding.codes if c.code_type=='cpt']}"
        )
        try:
            state.denial_mgmt.appeal_letter = chat_text(APPEAL_SYSTEM, user)
        except Exception as exc:
            state.errors.append(f"appeal_llm_error: {exc}")
            state.denial_mgmt.appeal_letter = ""
    else:
        # CO-45 / PR-1 / unknown -> write off (not a true denial to chase).
        state.denial_mgmt.strategy = "write_off"

    state.denial_mgmt.handled = True

    # Persist: update the denial row with strategy + appeal letter, audit.
    session = SessionLocal()
    try:
        denial = (session.query(Denial)
                  .filter(Denial.claim_id == state.claim_id)
                  .order_by(Denial.created_at.desc())
                  .first())
        if denial:
            denial.appeal_status = state.denial_mgmt.strategy
            if state.denial_mgmt.appeal_letter:
                denial.appeal_letter = state.denial_mgmt.appeal_letter

        # If we corrected the codes, persist the corrected set.
        if state.denial_mgmt.strategy == "correct_resubmit":
            session.query(ClaimCode).filter(
                ClaimCode.claim_id == state.claim_id).delete()
            for c in state.coding.codes:
                session.add(ClaimCode(
                    claim_id=state.claim_id, code_type=c.code_type, code=c.code,
                    modifier=c.modifier, units=c.units, charge=c.charge))

        session.add(AuditEvent(
            tenant_id=state.tenant_id, claim_id=state.claim_id,
            actor="denial_mgmt_agent", action="denial_handled",
            payload={"carc": carc, "strategy": state.denial_mgmt.strategy,
                     "correction": state.denial_mgmt.correction_applied}))
        session.commit()
    finally:
        session.close()

    if state.denial_mgmt.strategy == "correct_resubmit":
        state.status = "APPEAL_DRAFTED"  # reuse status; resubmit node advances it
    elif state.denial_mgmt.strategy == "appeal":
        state.status = "APPEAL_DRAFTED"
    else:
        state.status = "DENIED"  # write-off stays denied, no further action

    return state
