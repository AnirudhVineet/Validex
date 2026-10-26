"""Application lifecycle: create, edit form data, submit / resubmit with version snapshots,
start scrutiny, and the officer decisions. Status transitions are deterministic and audited.

Lifecycle (see docs/CONTRACTS.md):
  draft -submit-> submitted -start_scrutiny-> under_scrutiny
  under_scrutiny -return_for_correction-> returned_for_correction -resubmit-> submitted (version+1)
  under_scrutiny -escalate-> escalated (senior decides)
  under_scrutiny / escalated -mark_scrutiny_complete-> scrutiny_complete
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import ApplicationCategory, ApplicationStatus, FindingStatus, Role, Severity
from app.models import Application, ApplicationDocument, ApplicationVersion, Finding, Notification, ReviewAction, User
from app.models.base import utcnow
from app.services import audit
from app.services.access import conflict, ensure_applicant_owner, ensure_editable, ensure_reviewer, forbidden
from app.services.rules.loader import get_checklist

BLOCKING_SEVERITIES = {Severity.critical, Severity.high}
# Inspector evidence is stored as a document but is never part of the checklist or validation.
INSPECTION_DOC_TYPE = "inspection_evidence"
MIN_REASON = 5


def create_application(db: Session, user: User, category: ApplicationCategory, academic_year: str,
                       form_data: dict) -> Application:
    if user.role != Role.applicant or not user.institution_id:
        raise forbidden("Only applicants linked to an institution can create applications")
    _validate_form(db, category, form_data)
    app = Application(institution_id=user.institution_id, category=category,
                      academic_year=academic_year, form_data=form_data, created_by=user.id)
    db.add(app)
    db.flush()
    audit.log(db, user.id, "application.created", "application", app.id,
              {"category": category.value, "academic_year": academic_year})
    return app


def _validate_form(db: Session, category: ApplicationCategory, form_data: dict) -> None:
    """Check form values against the checklist's form_fields (types only; required checked at submit)."""
    _, checklist = get_checklist(db, category.value)
    allowed = {f.name: f for f in checklist.form_fields}
    for key, value in form_data.items():
        spec = allowed.get(key)
        if spec is None:
            raise conflict(f"Unknown form field '{key}' for this category")
        if spec.type == "integer" and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            raise conflict(f"'{key}' must be a non-negative whole number")


def missing_form_fields(db: Session, app: Application) -> list[str]:
    _, checklist = get_checklist(db, app.category.value)
    return [f.label for f in checklist.form_fields
            if f.required and (app.form_data or {}).get(f.name) in (None, "")]


def update_form(db: Session, user: User, app: Application, form_data: dict) -> Application:
    ensure_applicant_owner(user, app)
    ensure_editable(app)
    _validate_form(db, app.category, form_data)
    app.form_data = {**(app.form_data or {}), **form_data}
    audit.log(db, user.id, "application.updated", "application", app.id, {"form_data": app.form_data})
    return app


def current_documents(db: Session, app: Application) -> list[ApplicationDocument]:
    return list(db.execute(
        select(ApplicationDocument)
        .where(ApplicationDocument.application_id == app.id, ApplicationDocument.is_current,
               ApplicationDocument.doc_type != INSPECTION_DOC_TYPE)
        .order_by(ApplicationDocument.doc_type)
    ).scalars())


def _snapshot(db: Session, app: Application) -> dict:
    return {
        "category": app.category.value,
        "academic_year": app.academic_year,
        "form_data": app.form_data,
        "documents": [{"id": d.id, "doc_type": d.doc_type, "sha256": d.sha256,
                       "filename": d.original_filename} for d in current_documents(db, app)],
    }


def submit(db: Session, user: User, app: Application) -> Application:
    """Submit a draft, or resubmit after 'return for correction'. Snapshots the version."""
    ensure_applicant_owner(user, app)
    ensure_editable(app)
    missing = missing_form_fields(db, app)
    if missing:
        raise conflict(f"Fill in required form fields first: {', '.join(missing)}")
    resubmit = app.status == ApplicationStatus.returned_for_correction
    db.add(ApplicationVersion(application_id=app.id, version=app.current_version,
                              submitted_by=user.id, snapshot=_snapshot(db, app)))
    app.status = ApplicationStatus.submitted
    app.submitted_at = utcnow()
    audit.log(db, user.id, "application.resubmitted" if resubmit else "application.submitted",
              "application", app.id, {"version": app.current_version})
    return app


def start_scrutiny(db: Session, user: User, app: Application) -> Application:
    ensure_reviewer(user)
    if app.status != ApplicationStatus.submitted:
        raise conflict(f"Scrutiny can only start on a submitted application (now '{app.status.value}')")
    app.status = ApplicationStatus.under_scrutiny
    audit.log(db, user.id, "application.scrutiny_started", "application", app.id,
              {"version": app.current_version})
    return app


DECISIONS = {"mark_scrutiny_complete", "return_for_correction", "escalate"}


def _allowed_decision(user: User, app: Application, decision: str) -> bool:
    if user.role == Role.scrutiny_officer:
        return app.status == ApplicationStatus.under_scrutiny
    if user.role == Role.senior_authority:
        # Senior authority decides escalated cases; escalating further is not a senior action.
        return (app.status in (ApplicationStatus.under_scrutiny, ApplicationStatus.escalated)
                and decision != "escalate")
    return False


def blocking_findings(db: Session, app: Application, run_id: str | None) -> list[Finding]:
    if run_id is None:
        return []
    return list(db.execute(select(Finding).where(
        Finding.validation_run_id == run_id, Finding.status == FindingStatus.open,
        Finding.severity.in_(BLOCKING_SEVERITIES))).scalars())


def decide(db: Session, user: User, app: Application, decision: str, reason: str,
           latest_run_id: str | None) -> Application:
    """Officer / senior decision on the application. A reason is always required."""
    ensure_reviewer(user)
    if decision not in DECISIONS:
        raise conflict(f"Unknown decision '{decision}'")
    if len(reason.strip()) < MIN_REASON:
        raise conflict("A reason (at least 5 characters) is required")
    if not _allowed_decision(user, app, decision):
        raise conflict(f"'{decision}' is not allowed for a {user.role.value} while the application "
                       f"is '{app.status.value}'")
    if decision == "mark_scrutiny_complete":
        blocking = blocking_findings(db, app, latest_run_id)
        if blocking:
            raise conflict(f"{len(blocking)} open critical/high finding(s) must be resolved, dismissed "
                           "or escalated first")
        app.status = ApplicationStatus.scrutiny_complete
    elif decision == "return_for_correction":
        app.status = ApplicationStatus.returned_for_correction
        app.current_version += 1  # the next submission is a new version
        for applicant in db.execute(select(User).where(User.institution_id == app.institution_id,
                                                       User.role == Role.applicant)).scalars():
            db.add(Notification(user_id=applicant.id, application_id=app.id, kind="awaiting_correction",
                                message=f"Application returned for correction: {reason.strip()}"))
    else:
        app.status = ApplicationStatus.escalated

    db.add(ReviewAction(actor_id=user.id, target_type="application", target_id=app.id,
                        action=decision, reason=reason.strip()))
    audit.log(db, user.id, f"application.{decision}", "application", app.id,
              {"reason": reason.strip(), "new_status": app.status.value})
    return app
