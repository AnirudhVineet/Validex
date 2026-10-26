from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.enums import Role
from app.models import Application, Finding, User, ValidationRun
from app.routes.applications import load_application
from app.schemas import FindingOut, ReportOut, ReviewRequest, ValidationRunOut
from app.services import review
from app.services.access import ensure_view
from app.services.report import build_report
from app.services.validation import latest_run, run_validation

router = APIRouter(tags=["validation"])


@router.post("/api/applications/{application_id}/validate", response_model=ValidationRunOut)
def validate(application_id: str, precheck: bool = False, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)) -> ValidationRun:
    """precheck=true: applicant pre-check on a draft. Otherwise: officer re-run on a submitted case."""
    app = load_application(db, application_id)
    ensure_view(user, app)
    run = run_validation(db, user, app, precheck=precheck)
    db.commit()
    return run


@router.get("/api/applications/{application_id}/runs", response_model=list[ValidationRunOut])
def runs(application_id: str, db: Session = Depends(get_db),
         user: User = Depends(get_current_user)) -> list[ValidationRun]:
    app = load_application(db, application_id)
    ensure_view(user, app)
    query = select(ValidationRun).where(ValidationRun.application_id == app.id)
    if user.role != Role.applicant:
        query = query.where(ValidationRun.is_precheck.is_(False))
    return list(db.execute(query.order_by(ValidationRun.started_at.desc())).scalars())


@router.get("/api/applications/{application_id}/report", response_model=ReportOut)
def report(application_id: str, run_id: str | None = None, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)) -> dict:
    """Validation report. Filtered in the backend: applicants only get applicant-visible findings."""
    return build_report(db, user, load_application(db, application_id), run_id)


@router.post("/api/findings/{finding_id}/review", response_model=FindingOut)
def review_finding(finding_id: str, body: ReviewRequest, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> Finding:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")
    app = db.get(Application, finding.application_id)
    ensure_view(user, app)
    current = latest_run(db, app, include_precheck=False)
    if current is None or finding.validation_run_id != current.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only findings of the latest validation run can be reviewed")
    review.act_on_finding(db, user, app, finding, body.action, body.reason)
    db.commit()
    return finding
