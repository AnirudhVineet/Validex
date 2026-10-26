"""Alerts: deterministic notifications created from findings, verifications and workflow state.

Kinds: missing, expired, pending_verification, anomaly, awaiting_correction.
Applicants are only told about things they can see (missing / expired documents, corrections);
anomaly and verification alerts go to scrutiny officers only. Duplicates (same user,
application, kind and message, still unread) are not created twice.
"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import ApplicationStatus, FindingCategory, FindingStatus, Role, VerificationStatus
from app.models import Application, Finding, Institution, Notification, User, ValidationRun, VerificationRequest
from app.models.base import utcnow
from app.services.verification import latest_verifications


def _notify(db: Session, user_id: str, app_id: str, kind: str, message: str) -> bool:
    exists = db.execute(select(Notification.id).where(
        Notification.user_id == user_id, Notification.application_id == app_id, Notification.kind == kind,
        Notification.message == message, Notification.read_at.is_(None))).first()
    if exists:
        return False
    db.add(Notification(user_id=user_id, application_id=app_id, kind=kind, message=message))
    return True


def _users(db: Session, role: Role, institution_id: str | None = None) -> list[User]:
    query = select(User).where(User.role == role, User.is_active)
    if institution_id:
        query = query.where(User.institution_id == institution_id)
    return list(db.execute(query).scalars())


def after_validation(db: Session, app: Application, run: ValidationRun) -> int:
    """Create alerts for one official validation run. Returns how many were created."""
    if run.is_precheck:
        return 0
    inst = db.get(Institution, app.institution_id)
    findings = list(db.execute(select(Finding).where(
        Finding.validation_run_id == run.id, Finding.status == FindingStatus.open)).scalars())
    created = 0
    missing = [f for f in findings if f.rule_id == "COMP-001"]
    expired = [f for f in findings if f.rule_id == "EXP-001"]
    anomalies = [f for f in findings if f.category == FindingCategory.anomaly]

    for applicant in _users(db, Role.applicant, app.institution_id):
        if missing:
            created += _notify(db, applicant.id, app.id, "missing",
                               f"{len(missing)} required document(s) missing: " + "; ".join(f.title for f in missing))
        if expired:
            created += _notify(db, applicant.id, app.id, "expired",
                               f"{len(expired)} document(s) expired: " + "; ".join(f.title for f in expired))
    if anomalies:
        for officer in _users(db, Role.scrutiny_officer):
            created += _notify(db, officer.id, app.id, "anomaly",
                               f"{inst.name}: {len(anomalies)} preliminary anomaly indicator(s) need manual review")
    return created


def pending_verifications(db: Session) -> int:
    """Alert officers about verifications still pending longer than the configured threshold."""
    cutoff = utcnow() - timedelta(hours=settings.pending_verification_alert_hours)
    created = 0
    open_statuses = (ApplicationStatus.submitted, ApplicationStatus.under_scrutiny, ApplicationStatus.escalated)
    apps = db.execute(select(Application).where(Application.status.in_(open_statuses))).scalars()
    officers = _users(db, Role.scrutiny_officer)
    for app in apps:
        stale = [v for v in latest_verifications(db, app).values()
                 if v.status == VerificationStatus.pending and v.requested_at < cutoff]
        if not stale:
            continue
        inst = db.get(Institution, app.institution_id)
        for officer in officers:
            created += _notify(db, officer.id, app.id, "pending_verification",
                               f"{inst.name}: {len(stale)} issuer verification(s) pending for more than "
                               f"{settings.pending_verification_alert_hours} h")
    return created


def for_user(db: Session, user: User, unread_only: bool = False) -> list[Notification]:
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    return list(db.execute(query.order_by(Notification.created_at.desc()).limit(100)).scalars())


def stale_pending_count(db: Session) -> int:
    cutoff = utcnow() - timedelta(hours=settings.pending_verification_alert_hours)
    return len(list(db.execute(select(VerificationRequest.id).where(
        VerificationRequest.status == VerificationStatus.pending,
        VerificationRequest.requested_at < cutoff)).all()))
