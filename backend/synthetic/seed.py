"""Seed the database with synthetic tenants, users, payers, and claims.

Run:  python -m synthetic.seed
Idempotent-ish: wipes and reseeds the synthetic tables each run.
"""
from __future__ import annotations
import random

from rich.console import Console
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.db.models import (
    Tenant, User, Payer, Patient, Encounter, Claim, ClaimCode, AuditEvent,
    EligibilityCheck, ScrubResult, Remittance, Denial,
)
from app.db.repositories.base import TenantRepository
from synthetic.generator import generate_batch, PAYERS

console = Console()

TENANTS = [
    {"name": "Riverside Family Practice", "npi": "1234567890"},
    {"name": "Summit Orthopedics Group", "npi": "0987654321"},
]
ROLES = ["admin", "manager", "biller", "practice"]
CLAIMS_PER_TENANT = 40


def wipe(session):
    # Order matters for FKs; children first.
    for model in (Denial, Remittance, ScrubResult, EligibilityCheck, ClaimCode,
                  Claim, Encounter, Patient, AuditEvent, User, Payer, Tenant):
        session.execute(delete(model))
    session.commit()


def seed():
    session = SessionLocal()
    try:
        wipe(session)
        console.print("[yellow]Wiped existing data.[/yellow]")

        # Payers are global (not tenant-scoped).
        payer_rows = {}
        for p in PAYERS:
            row = Payer(name=p["name"], payer_type=p["payer_type"],
                        denial_profile={"denial_rate": p["denial_rate"]})
            session.add(row)
            session.flush()
            payer_rows[p["name"]] = row
        console.print(f"Seeded [cyan]{len(payer_rows)}[/cyan] payers.")

        for t in TENANTS:
            tenant = Tenant(name=t["name"], npi=t["npi"])
            session.add(tenant)
            session.flush()

            # Users across roles.
            for role in ROLES:
                session.add(User(
                    tenant_id=tenant.id, name=f"{role.title()} User",
                    role=role, email=f"{role}@{tenant.id[:8]}.demo",
                ))

            # Tenant-scoped repositories ? isolation enforced here.
            patient_repo = TenantRepository(session, Patient, tenant.id)
            enc_repo = TenantRepository(session, Encounter, tenant.id)
            claim_repo = TenantRepository(session, Claim, tenant.id)
            audit_repo = TenantRepository(session, AuditEvent, tenant.id)

            for gc in generate_batch(CLAIMS_PER_TENANT):
                payer_row = payer_rows[gc.payer["name"]]
                patient = patient_repo.add(Patient(
                    synthetic_mrn=gc.synthetic_mrn, name=gc.patient_name,
                    dob=gc.dob, gender=gc.gender, member_id=gc.member_id,
                    payer_id=payer_row.id,
                ))
                enc = enc_repo.add(Encounter(
                    patient_id=patient.id, dos=gc.dos, pos=gc.pos,
                    provider_npi=gc.provider_npi, clinical_note=gc.clinical_note,
                    dx_hints=gc.dx_hints,
                ))
                claim = claim_repo.add(Claim(
                    patient_id=patient.id, encounter_id=enc.id,
                    status="DRAFT", total_charge=gc.cpt_charge,
                ))
                # Codes attached to the claim (not tenant-scoped directly).
                session.add(ClaimCode(
                    claim_id=claim.id, code_type="cpt", code=gc.cpt,
                    modifier=gc.modifier, units=1, charge=gc.cpt_charge,
                ))
                session.add(ClaimCode(
                    claim_id=claim.id, code_type="icd10", code=gc.icd10,
                ))
                audit_repo.add(AuditEvent(
                    claim_id=claim.id, actor="seed",
                    action="claim_created",
                    payload={"defect": gc.defect, "payer": gc.payer["name"]},
                ))

            console.print(f"Seeded tenant [green]{tenant.name}[/green] "
                          f"with {CLAIMS_PER_TENANT} claims.")

        session.commit()

        # Verify isolation: each tenant repo sees only its own claims.
        console.print("\n[bold]Isolation check:[/bold]")
        tenants = session.query(Tenant).all()
        for tenant in tenants:
            repo = TenantRepository(session, Claim, tenant.id)
            console.print(f"  {tenant.name}: [cyan]{repo.count()}[/cyan] claims visible")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
