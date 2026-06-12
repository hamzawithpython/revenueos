"""Scrubber agent ? rule-based clean-claim checks before submission.

Deterministic, mirroring real CCI/LCD edits: missing required modifiers,
diagnosis/procedure mismatches, and missing code types. A claim with edits
is marked not-clean and flagged for review but still proceeds, so the
payer mock can exercise the denial path realistically.
"""
from __future__ import annotations
from pathlib import Path
import yaml

from app.agents.state import ClaimState
from app.db.session import SessionLocal
from app.db.models import ScrubResult, AuditEvent

PATTERNS = Path(__file__).resolve().parents[2] / "synthetic" / "patterns"


def _load_procedures() -> dict[str, dict]:
    with open(PATTERNS / "procedures.yaml", "r", encoding="utf-8") as f:
        rows = yaml.safe_load(f)["procedures"]
    return {r["cpt"]: r for r in rows}


PROCEDURES = _load_procedures()


def scrub_claim(state: ClaimState) -> ClaimState:
    """Pure scrub logic: rule checks only, NO persistence. Used by both
    run_scrubber (which persists) and the eval harness (which does not)."""
    edits: list[str] = []

    cpt_codes = [c for c in state.coding.codes if c.code_type == "cpt"]
    icd_codes = [c for c in state.coding.codes if c.code_type == "icd10"]
    dx_set = {c.code for c in icd_codes}

    if not cpt_codes:
        edits.append("SCRUB-001 No procedure (CPT) code present")
    if not icd_codes:
        edits.append("SCRUB-002 No diagnosis (ICD-10) code present")

    for cpt in cpt_codes:
        proc = PROCEDURES.get(cpt.code)
        if not proc:
            edits.append(f"SCRUB-003 Unknown CPT code {cpt.code}")
            continue
        if proc.get("requires_modifier") and not cpt.modifier:
            edits.append(
                f"SCRUB-004 CPT {cpt.code} requires a modifier (e.g. LT/RT) but none present")
        valid_dx = set(proc.get("valid_dx", []))
        if valid_dx and dx_set and not (dx_set & valid_dx):
            edits.append(
                f"SCRUB-005 Diagnosis {sorted(dx_set)} inconsistent with procedure {cpt.code}")

    state.scrub.scrubbed = True
    state.scrub.clean = len(edits) == 0
    state.scrub.edits = edits
    if not state.scrub.clean:
        state.needs_human_review = True
    return state


def run_scrubber(state: ClaimState) -> ClaimState:
    state = scrub_claim(state)
    clean = state.scrub.clean
    edits = state.scrub.edits

    session = SessionLocal()
    try:
        session.add(ScrubResult(
            claim_id=state.claim_id, clean=clean, edits=edits,
        ))
        session.add(AuditEvent(
            tenant_id=state.tenant_id, claim_id=state.claim_id,
            actor="scrubber_agent", action="claim_scrubbed",
            payload={"clean": clean, "edit_count": len(edits)},
        ))
        session.commit()
    finally:
        session.close()

    state.status = "SCRUBBED"
    return state

