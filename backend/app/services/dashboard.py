"""Role-specific dashboard counts. Phase 0: real queries, mostly zeros until data exists."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import ApplicationStatus, FindingStatus, Role
from app.models import Application, AuditEvent, Finding, RuleSetVersion, User


def _status_counts(db: Session, institution_id: str | None = None) -> dict[str, int]:
    query = select(Application.status, func.count()).group_by(Application.status)
    if institution_id is not None:
        query = query.where(Application.institution_id == institution_id)
    counts = {s.value: 0 for s in ApplicationStatus}
    for status, n in db.execute(query).all():
        counts[status.value] = n
    return counts


def summary_for(db: Session, user: User) -> dict:
    """Return {role, counts, notes} for the given user's dashboard."""
    if user.role == Role.applicant:
        counts = _status_counts(db, user.institution_id) if user.institution_id else {}
        return {"role": user.role, "counts": counts, "notes": []}

    if user.role in (Role.scrutiny_officer, Role.senior_authority):
        counts = _status_counts(db)
        counts["open_findings"] = db.scalar(
            select(func.count()).select_from(Finding).where(Finding.status == FindingStatus.open)
        ) or 0
        return {"role": user.role, "counts": counts, "notes": []}

    if user.role == Role.inspector:
        flagged = db.scalar(
            select(func.count()).select_from(Application)
            .where(Application.status == ApplicationStatus.escalated)
        ) or 0
        return {"role": user.role, "counts": {"flagged_cases": flagged}, "notes": []}

    # admin
    return {
        "role": user.role,
        "counts": {
            "users": db.scalar(select(func.count()).select_from(User)) or 0,
            "rule_set_versions": db.scalar(select(func.count()).select_from(RuleSetVersion)) or 0,
            "audit_events": db.scalar(select(func.count()).select_from(AuditEvent)) or 0,
        },
        "notes": [],
    }
