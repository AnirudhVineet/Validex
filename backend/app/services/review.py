"""Officer / senior actions on individual findings. A reason is always required and audited."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.enums import ApplicationStatus, FindingStatus, Role
from app.models import Application, Finding, ReviewAction, User
from app.services import audit
from app.services.access import ensure_reviewer

ACTIONS = {"resolve": FindingStatus.resolved, "dismiss": FindingStatus.dismissed,
           "escalate": FindingStatus.escalated}
REVIEWABLE_APP_STATUSES = {ApplicationStatus.under_scrutiny, ApplicationStatus.escalated}


def act_on_finding(db: Session, user: User, app: Application, finding: Finding,
                   action: str, reason: str) -> Finding:
    ensure_reviewer(user)
    if action not in ACTIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown action '{action}'")
    if len(reason.strip()) < 5:
        raise HTTPException(status.HTTP_409_CONFLICT, "A reason (at least 5 characters) is required")
    if app.status not in REVIEWABLE_APP_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Findings can be reviewed only during scrutiny (now '{app.status.value}')")
    allowed_from = {FindingStatus.open}
    if user.role == Role.senior_authority:
        allowed_from.add(FindingStatus.escalated)
    if finding.status not in allowed_from:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Finding is '{finding.status.value}' and cannot be changed by a {user.role.value}")

    old = finding.status
    finding.status = ACTIONS[action]
    finding.reviewed_by = user.id
    finding.review_reason = reason.strip()
    db.add(ReviewAction(actor_id=user.id, target_type="finding", target_id=finding.id,
                        action=action, reason=reason.strip()))
    audit.log(db, user.id, f"finding.{finding.status.value}", "finding", finding.id,
              {"application_id": app.id, "rule_id": finding.rule_id, "from": old.value,
               "to": finding.status.value, "reason": reason.strip()})
    return finding
