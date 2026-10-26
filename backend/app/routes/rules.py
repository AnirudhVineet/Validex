from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.enums import Role
from app.models import RuleSetVersion, User
from app.schemas import RerunResult, RuleSave, RuleSetDetail, RuleSetVersionOut, RuleText, RuleValidation
from app.services import rule_editor
from app.services.rules.loader import get_rule_set

router = APIRouter(prefix="/api/rules", tags=["rules"])
_readers = require_roles(Role.scrutiny_officer, Role.senior_authority, Role.admin)
_editors = require_roles(Role.senior_authority, Role.admin)


@router.get("", response_model=RuleSetDetail)
def active_rules(db: Session = Depends(get_db), _: User = Depends(_readers)) -> RuleSetVersion:
    row, _ = get_rule_set(db)
    db.commit()
    return row


@router.get("/versions", response_model=list[RuleSetVersionOut])
def rule_versions(db: Session = Depends(get_db), _: User = Depends(_readers)) -> list[RuleSetVersion]:
    return rule_editor.versions(db)


@router.post("/validate", response_model=RuleValidation)
def validate_rules(body: RuleText, _: User = Depends(_editors)) -> dict:
    """Check YAML without saving. Officers cannot use the editor."""
    return rule_editor.validate_text(body.content_yaml)


@router.put("", response_model=RuleSetDetail)
def save_rules(body: RuleSave, db: Session = Depends(get_db), user: User = Depends(_editors)) -> RuleSetVersion:
    """Validate and save as a new version (previous version kept, deactivated)."""
    row = rule_editor.save_new_version(db, user, body.content_yaml, body.reason)
    db.commit()
    return row


@router.post("/rerun", response_model=RerunResult)
def rerun(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """Re-run official validation on open cases with the active rules. Old runs are preserved."""
    result = rule_editor.rerun_open_cases(db, user)
    db.commit()
    return result
