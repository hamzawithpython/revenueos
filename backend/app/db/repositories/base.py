"""Tenant-scoped repository base class.

Every query is automatically filtered by tenant_id. This is the single
enforcement point for multi-tenant isolation ? agent and API code never
write raw queries, so cross-tenant leakage is structurally prevented.
"""
from typing import Generic, TypeVar, Type, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import Base

ModelT = TypeVar("ModelT", bound=Base)


class TenantRepository(Generic[ModelT]):
    """Base repository scoped to a single tenant.

    Subclass per model, or instantiate directly with a model class.
    The tenant_id is bound at construction and applied to every operation
    on models that have a tenant_id column.
    """

    def __init__(self, session: Session, model: Type[ModelT], tenant_id: str):
        self.session = session
        self.model = model
        self.tenant_id = tenant_id
        self._tenant_scoped = hasattr(model, "tenant_id")

    def _base_query(self):
        stmt = select(self.model)
        if self._tenant_scoped:
            stmt = stmt.where(self.model.tenant_id == self.tenant_id)
        return stmt

    def get(self, id_: str) -> Optional[ModelT]:
        stmt = self._base_query().where(self.model.id == id_)
        return self.session.execute(stmt).scalar_one_or_none()

    def list(self, limit: int = 100):
        stmt = self._base_query().limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def list_by(self, **filters):
        stmt = self._base_query()
        for field, value in filters.items():
            stmt = stmt.where(getattr(self.model, field) == value)
        return list(self.session.execute(stmt).scalars().all())

    def add(self, obj: ModelT) -> ModelT:
        # Force the tenant_id on write so callers cannot misassign it.
        if self._tenant_scoped:
            obj.tenant_id = self.tenant_id
        self.session.add(obj)
        self.session.flush()
        return obj

    def count(self) -> int:
        return len(self.list(limit=10_000))
