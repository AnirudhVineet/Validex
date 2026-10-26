from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.enums import Role
from app.models import AuditEvent, User
from app.schemas import AuditEventOut, ChainVerifyResult
from app.services import audit

router = APIRouter(prefix="/api/audit", tags=["audit"])
_audit_readers = require_roles(Role.scrutiny_officer, Role.senior_authority, Role.admin)


@router.get("", response_model=list[AuditEventOut])
def list_events(
    limit: int = Query(100, ge=1, le=1000),
    target_id: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(_audit_readers),
) -> list[AuditEvent]:
    query = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if target_id:
        query = query.where(AuditEvent.target_id == target_id)
    return list(db.execute(query).scalars())


@router.get("/verify", response_model=ChainVerifyResult)
def verify(db: Session = Depends(get_db), _: User = Depends(_audit_readers)) -> dict:
    return audit.verify_chain(db)
