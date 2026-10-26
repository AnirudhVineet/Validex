from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.enums import ApplicationStatus, FindingStatus, Role, Severity
from app.models import Application, ApplicationVersion, Finding, Institution, User
from app.schemas import (
    ApplicationCreate, ApplicationListItem, ApplicationOut, ApplicationUpdate, ApplicationVersionOut,
    ChecklistItemOut, DecisionRequest,
)
from app.services import applications as svc
from app.services.access import STAFF, can_view, ensure_view
from app.services.report import checklist_status
from app.services.validation import latest_run, run_validation

router = APIRouter(prefix="/api/applications", tags=["applications"])


def load_application(db: Session, application_id: str) -> Application:
    app = db.get(Application, application_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return app


@router.post("", response_model=ApplicationOut, status_code=201)
def create(body: ApplicationCreate, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)) -> Application:
    app = svc.create_application(db, user, body.category, body.academic_year, body.form_data)
    db.commit()
    return app


@router.get("", response_model=list[ApplicationListItem])
def list_applications(status_filter: ApplicationStatus | None = Query(None, alias="status"),
                      db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    query = select(Application, Institution.name).join(Institution).order_by(Application.updated_at.desc())
    if user.role == Role.applicant:
        query = query.where(Application.institution_id == user.institution_id)
    if status_filter is not None:
        query = query.where(Application.status == status_filter)
    out = []
    for app, inst_name in db.execute(query).all():
        if not can_view(user, app):
            continue
        item = ApplicationOut.model_validate(app).model_dump()
        item["institution_name"] = inst_name
        if user.role in STAFF:
            run = latest_run(db, app, include_precheck=False)
            if run is not None:
                base = select(func.count()).select_from(Finding).where(
                    Finding.validation_run_id == run.id, Finding.status == FindingStatus.open)
                item["open_findings"] = db.scalar(base) or 0
                item["critical_findings"] = db.scalar(base.where(Finding.severity == Severity.critical)) or 0
        out.append(item)
    return out


@router.get("/{application_id}", response_model=ApplicationOut)
def get_one(application_id: str, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)) -> Application:
    app = load_application(db, application_id)
    ensure_view(user, app)
    return app


@router.patch("/{application_id}", response_model=ApplicationOut)
def update(application_id: str, body: ApplicationUpdate, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)) -> Application:
    app = svc.update_form(db, user, load_application(db, application_id), body.form_data)
    db.commit()
    return app


@router.get("/{application_id}/checklist", response_model=list[ChecklistItemOut])
def checklist(application_id: str, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)) -> list[dict]:
    app = load_application(db, application_id)
    ensure_view(user, app)
    return checklist_status(db, app)


@router.get("/{application_id}/versions", response_model=list[ApplicationVersionOut])
def versions(application_id: str, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)) -> list[ApplicationVersion]:
    app = load_application(db, application_id)
    ensure_view(user, app)
    return list(db.execute(select(ApplicationVersion).where(ApplicationVersion.application_id == app.id)
                           .order_by(ApplicationVersion.version)).scalars())


@router.post("/{application_id}/submit", response_model=ApplicationOut)
def submit(application_id: str, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)) -> Application:
    """Submit or resubmit. The official validation run happens immediately on submission."""
    app = svc.submit(db, user, load_application(db, application_id))
    run_validation(db, user, app, precheck=False, skip_permission=True)
    db.commit()
    return app


@router.post("/{application_id}/start-scrutiny", response_model=ApplicationOut)
def start_scrutiny(application_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> Application:
    app = svc.start_scrutiny(db, user, load_application(db, application_id))
    db.commit()
    return app


@router.post("/{application_id}/decision", response_model=ApplicationOut)
def decision(application_id: str, body: DecisionRequest, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)) -> Application:
    """Mark scrutiny complete / Return for correction / Escalate. Never approve or reject."""
    app = load_application(db, application_id)
    ensure_view(user, app)
    run = latest_run(db, app, include_precheck=False)
    svc.decide(db, user, app, body.decision, body.reason, run.id if run else None)
    db.commit()
    return app
