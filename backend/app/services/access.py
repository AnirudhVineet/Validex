"""Who may see or change an application. Used by every route; the backend is the boundary."""
from fastapi import HTTPException, status

from app.enums import ApplicationStatus, Role
from app.models import Application, User

STAFF = {Role.scrutiny_officer, Role.senior_authority, Role.admin}
REVIEWERS = {Role.scrutiny_officer, Role.senior_authority}
EDITABLE = {ApplicationStatus.draft, ApplicationStatus.returned_for_correction}


def forbidden(detail: str = "Forbidden") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def can_view(user: User, app: Application) -> bool:
    if user.role == Role.applicant:
        return app.institution_id == user.institution_id
    if user.role in STAFF:
        # Drafts are the applicant's private workspace until first submitted.
        return app.status != ApplicationStatus.draft or app.submitted_at is not None
    if user.role == Role.inspector:
        return app.status == ApplicationStatus.escalated
    return False


def ensure_view(user: User, app: Application) -> None:
    if not can_view(user, app):
        raise forbidden("You cannot view this application")


def ensure_applicant_owner(user: User, app: Application) -> None:
    if user.role != Role.applicant or app.institution_id != user.institution_id:
        raise forbidden("Only the applicant institution can do this")


def ensure_editable(app: Application) -> None:
    if app.status not in EDITABLE:
        raise conflict(f"Application is '{app.status.value}' and cannot be edited now")


def ensure_reviewer(user: User) -> None:
    if user.role not in REVIEWERS:
        raise forbidden("Only scrutiny officers and senior authorities can review")
