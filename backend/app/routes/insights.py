from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_user, require_roles
from app.enums import Role
from app.models import InspectionRecord, User
from app.routes.applications import load_application
from app.schemas import (
    CaseSummary, ExpiryForecast, InfrastructureAdvisory, InspectionOut, LetterDraft, SeniorOverview, TimeSaved,
)
from app.services import insights, inspections, letters, summary
from app.services.access import ensure_view, forbidden

router = APIRouter(tags=["insights"])
_staff = require_roles(Role.scrutiny_officer, Role.senior_authority, Role.admin)
_senior = require_roles(Role.senior_authority, Role.admin)
_case_viewers = {Role.scrutiny_officer, Role.senior_authority, Role.admin, Role.inspector}


@router.get("/api/dashboard/expiry-forecast", response_model=ExpiryForecast)
def expiry_forecast(days: int = Query(90, ge=1, le=730), db: Session = Depends(get_db),
                    _: User = Depends(_staff)) -> dict:
    return insights.expiry_forecast(db, days)


@router.get("/api/dashboard/senior", response_model=SeniorOverview)
def senior_overview(db: Session = Depends(get_db), _: User = Depends(_senior)) -> dict:
    return insights.senior_overview(db)


@router.get("/api/dashboard/time-saved", response_model=TimeSaved)
def time_saved(db: Session = Depends(get_db), _: User = Depends(_staff)) -> dict:
    return insights.time_saved(db)


@router.post("/api/applications/{application_id}/inspections", response_model=InspectionOut, status_code=201)
async def add_inspection(application_id: str, notes: str = Form(""), evidence_label: str | None = Form(None),
                         file: UploadFile | None = File(None), db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)) -> InspectionRecord:
    app = load_application(db, application_id)
    data = await file.read(settings.max_upload_bytes + 1) if file is not None else None
    record = inspections.add_inspection(db, user, app, notes, evidence_label,
                                        file.filename if file is not None else None, data or None)
    db.commit()
    return record


@router.get("/api/applications/{application_id}/inspections", response_model=list[InspectionOut])
def list_inspections(application_id: str, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)) -> list[InspectionRecord]:
    app = load_application(db, application_id)
    ensure_view(user, app)
    if user.role not in _case_viewers:
        raise forbidden("Inspection records are for scrutiny staff and inspectors")
    return inspections.records(db, app)


@router.get("/api/applications/{application_id}/infrastructure", response_model=InfrastructureAdvisory)
def infrastructure(application_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> dict:
    app = load_application(db, application_id)
    ensure_view(user, app)
    if user.role not in _case_viewers:
        raise forbidden("The infrastructure advisory is for scrutiny staff and inspectors")
    return inspections.advisory(db, app)


@router.post("/api/applications/{application_id}/deficiency-letter", response_model=LetterDraft)
def deficiency_letter(application_id: str, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)) -> dict:
    """Template-based DRAFT for the officer to edit. Applicant-visible findings only."""
    app = load_application(db, application_id)
    ensure_view(user, app)
    result = letters.draft(db, user, app)
    db.commit()
    return result


@router.post("/api/applications/{application_id}/summary", response_model=CaseSummary)
def case_summary(application_id: str, db: Session = Depends(get_db), user: User = Depends(_staff)) -> dict:
    """Optional LLM summary grounded in finding ids. Disabled by default; never affects validation."""
    app = load_application(db, application_id)
    ensure_view(user, app)
    result = summary.summarize(db, user, app)
    db.commit()
    return result
