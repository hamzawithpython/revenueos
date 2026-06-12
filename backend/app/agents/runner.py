"""Run the supervisor over real DRAFT claims from the seeded DB.

Usage:
  python -m app.agents.runner            # process one claim
  python -m app.agents.runner --count 5  # process five

Loads a claim + its encounter + draft codes, builds ClaimState, runs the
graph, and prints the lifecycle transition.
"""
from __future__ import annotations
import argparse

from rich.console import Console

from app.db.session import SessionLocal
from app.db.models import Claim, Encounter, Patient, ClaimCode, Payer
from app.agents.state import ClaimState, CodeEntry
from app.agents.supervisor import supervisor

console = Console()


def load_state(session, claim: Claim) -> ClaimState:
    enc = session.get(Encounter, claim.encounter_id)
    patient = session.get(Patient, claim.patient_id)
    codes = session.query(ClaimCode).filter(ClaimCode.claim_id == claim.id).all()

    return ClaimState(
        claim_id=claim.id,
        tenant_id=claim.tenant_id,
        status=claim.status,
        member_id=patient.member_id,
        payer_name="",  # filled from payer lookup below
        patient_name=patient.name,
        dob=patient.dob,
        dos=enc.dos,
        pos=enc.pos,
        provider_npi=enc.provider_npi,
        clinical_note=enc.clinical_note,
        total_charge=claim.total_charge,
        coding={"coded": False,
                "codes": [CodeEntry(
                    code_type=c.code_type, code=c.code, modifier=c.modifier,
                    units=c.units, charge=c.charge) for c in codes],
                "rationale": ""},
    )


def _format_codes(codes) -> list[str]:
    """Render codes as 'code' or 'code/MOD' ? built outside any f-string
    to avoid backslash-in-expression restrictions."""
    out = []
    for c in codes:
        if c.modifier:
            out.append(c.code + "/" + c.modifier)
        else:
            out.append(c.code)
    return out


def main(count: int):
    session = SessionLocal()
    try:
        claims = session.query(Claim).filter(Claim.status == "DRAFT").limit(count).all()
        if not claims:
            console.print("[yellow]No DRAFT claims found. Re-seed if needed.[/yellow]")
            return

        for claim in claims:
            patient = session.get(Patient, claim.patient_id)
            payer = session.get(Payer, patient.payer_id)

            state = load_state(session, claim)
            state.payer_name = payer.name if payer else "Unknown"

            console.print(f"\n[bold]Claim {claim.id[:8]}[/bold] "
                          f"start status=[cyan]{state.status}[/cyan]")

            final = supervisor.invoke(state)
            final_state = final if isinstance(final, ClaimState) else ClaimState(**final)

            claim.status = final_state.status
            session.commit()

            elig = final_state.eligibility
            cod = final_state.coding
            scr = final_state.scrub
            adj = final_state.adjudication
            code_display = _format_codes(cod.codes)
            console.print(
                f"  eligibility: active={elig.active} copay={elig.copay} "
                f"plan='{elig.plan_name}'")
            console.print(f"  coding: {code_display}")
            scrub_msg = "clean" if scr.clean else f"{len(scr.edits)} edit(s): {scr.edits}"
            console.print(f"  scrub: {scrub_msg}")
            dm = final_state.denial_mgmt
            if adj.outcome == "PAID":
                console.print(
                    f"  adjudication: [green]PAID[/green] "
                    f"billed={adj.billed_amount} allowed={adj.allowed_amount} "
                    f"paid={adj.paid_amount} pr={adj.patient_responsibility}")
            elif adj.outcome == "DENIED":
                console.print(
                    f"  adjudication: [red]DENIED[/red] "
                    f"{adj.carc_code} - {adj.denial_reason}")
            elif not adj.accepted_by_clearinghouse and adj.submitted:
                console.print(
                    f"  adjudication: [yellow]CH REJECTED[/yellow] "
                    f"{adj.front_end_edits}")
            if dm.handled:
                if dm.strategy == "correct_resubmit":
                    resolved = dm.resolved_outcome or final_state.adjudication.outcome
                    console.print(
                        f"  denial mgmt: [cyan]CORRECT+RESUBMIT[/cyan] "
                        f"({dm.correction_applied}) -> resubmitted={dm.resubmitted} "
                        f"final={final_state.adjudication.outcome}")
                elif dm.strategy == "appeal":
                    preview = (dm.appeal_letter[:80] + "...") if dm.appeal_letter else "(no letter)"
                    console.print(f"  denial mgmt: [magenta]APPEAL[/magenta] letter: {preview}")
                else:
                    console.print(f"  denial mgmt: [yellow]WRITE-OFF[/yellow] ({adj.carc_code})")
            console.print(f"  end status=[green]{final_state.status}[/green] "
                          f"review={final_state.needs_human_review}")
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()
    main(args.count)


