"""SQLAlchemy ORM models. Every tenant-scoped table carries tenant_id.

SYNTHETIC DATA ONLY ? no real PHI ever populates these tables.
"""
from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    npi: Mapped[str] = mapped_column(String, nullable=True)
    plan_tier: Mapped[str] = mapped_column(String, default="demo")


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # admin/manager/biller/practice
    email: Mapped[str] = mapped_column(String, nullable=False)


class Payer(Base, TimestampMixin):
    __tablename__ = "payers"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    payer_type: Mapped[str] = mapped_column(String)  # medicare/medicaid/commercial
    denial_profile: Mapped[dict] = mapped_column(JSON, default=dict)  # drives mock behavior


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    synthetic_mrn: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    dob: Mapped[str] = mapped_column(String)
    gender: Mapped[str] = mapped_column(String)
    member_id: Mapped[str] = mapped_column(String)
    payer_id: Mapped[str] = mapped_column(ForeignKey("payers.id"))


class Encounter(Base, TimestampMixin):
    __tablename__ = "encounters"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    dos: Mapped[str] = mapped_column(String)  # date of service
    pos: Mapped[str] = mapped_column(String)  # place of service
    provider_npi: Mapped[str] = mapped_column(String)
    clinical_note: Mapped[str] = mapped_column(Text)
    dx_hints: Mapped[list] = mapped_column(JSON, default=list)


class Claim(Base, TimestampMixin):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    encounter_id: Mapped[str] = mapped_column(ForeignKey("encounters.id"))
    status: Mapped[str] = mapped_column(String, default="DRAFT", index=True)
    total_charge: Mapped[float] = mapped_column(Float, default=0.0)
    created_by: Mapped[str] = mapped_column(String, nullable=True)


class ClaimCode(Base, TimestampMixin):
    __tablename__ = "claim_codes"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    code_type: Mapped[str] = mapped_column(String)  # icd10 / cpt
    code: Mapped[str] = mapped_column(String)
    modifier: Mapped[str] = mapped_column(String, nullable=True)
    units: Mapped[int] = mapped_column(Integer, default=1)
    charge: Mapped[float] = mapped_column(Float, default=0.0)


class EligibilityCheck(Base, TimestampMixin):
    __tablename__ = "eligibility_checks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    copay: Mapped[float] = mapped_column(Float, default=0.0)
    deductible: Mapped[float] = mapped_column(Float, default=0.0)
    raw_271: Mapped[dict] = mapped_column(JSON, default=dict)


class ScrubResult(Base, TimestampMixin):
    __tablename__ = "scrub_results"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    clean: Mapped[bool] = mapped_column(Boolean, default=False)
    edits: Mapped[list] = mapped_column(JSON, default=list)  # CCI/LCD findings


class Remittance(Base, TimestampMixin):
    __tablename__ = "remittances"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    allowed_amount: Mapped[float] = mapped_column(Float, default=0.0)
    adjustments: Mapped[list] = mapped_column(JSON, default=list)
    raw_835: Mapped[dict] = mapped_column(JSON, default=dict)


class Denial(Base, TimestampMixin):
    __tablename__ = "denials"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    carc_code: Mapped[str] = mapped_column(String)
    rarc_code: Mapped[str] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    appealable: Mapped[bool] = mapped_column(Boolean, default=True)
    appeal_letter: Mapped[str] = mapped_column(Text, nullable=True)
    appeal_status: Mapped[str] = mapped_column(String, default="none")


class AuditEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True, nullable=True)
    actor: Mapped[str] = mapped_column(String)  # which agent / user
    action: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
