"""Mock clearinghouse service ? simulates 837 submission with front-end
edits returning a 999/277CA-style acknowledgement.

Front-end edits catch structural problems (missing NPI, empty code list,
malformed CPT) before the payer sees the claim ? mirroring real
clearinghouse behavior.
"""
from __future__ import annotations
import re
import uuid

from fastapi import FastAPI

from app.schemas.edi import ClaimSubmission, SubmissionAck

app = FastAPI(title="Mock Clearinghouse Service (837)")

CPT_RE = re.compile(r"^\d{5}$")
ICD_RE = re.compile(r"^[A-Z]\d{2}(\.\d{1,4})?$")


@app.get("/health")
def health():
    return {"status": "ok", "service": "clearinghouse"}


@app.post("/submit", response_model=SubmissionAck)
def submit_claim(claim: ClaimSubmission) -> SubmissionAck:
    edits: list[str] = []

    if not claim.provider_npi or len(claim.provider_npi) != 10:
        edits.append("A7:453 Missing or invalid billing provider NPI")
    if not claim.codes:
        edits.append("A7:454 Claim contains no service lines")

    has_cpt = any(c.code_type == "cpt" for c in claim.codes)
    has_icd = any(c.code_type == "icd10" for c in claim.codes)
    if not has_cpt:
        edits.append("A7:455 No procedure (CPT) code present")
    if not has_icd:
        edits.append("A7:456 No diagnosis (ICD-10) code present")

    for c in claim.codes:
        if c.code_type == "cpt" and not CPT_RE.match(c.code):
            edits.append(f"A7:457 Malformed CPT code: {c.code}")
        if c.code_type == "icd10" and not ICD_RE.match(c.code):
            edits.append(f"A7:458 Malformed ICD-10 code: {c.code}")

    accepted = len(edits) == 0
    return SubmissionAck(
        accepted=accepted,
        trace_number=f"TRC-{uuid.uuid4().hex[:12].upper()}",
        front_end_edits=edits,
    )
