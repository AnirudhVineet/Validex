"""Rule editing for admin / senior authority: validate, save as a new version, re-run.

Rules are never edited in place. Saving creates a new RuleSetVersion (version = latest + 1)
and deactivates the previous one. Re-running validation creates new runs; old runs and their
findings stay untouched for audit.
"""
import re

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import ApplicationStatus, RuleSetKind, Role
from app.models import Application, RuleSetVersion, User
from app.services import audit
from app.services.rules.loader import CORE_RULE_SET, RuleSetError, _hash, get_rule_set, parse_rule_set, version_label
from app.services.validation import run_validation

EDITORS = {Role.admin, Role.senior_authority}
RERUN_STATUSES = (ApplicationStatus.submitted, ApplicationStatus.under_scrutiny, ApplicationStatus.escalated)


def ensure_editor(user: User) -> None:
    if user.role not in EDITORS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admin and senior authority can edit rules")


def versions(db: Session, name: str = CORE_RULE_SET) -> list[RuleSetVersion]:
    get_rule_set(db, name)  # make sure v1 exists
    return list(db.execute(select(RuleSetVersion).where(
        RuleSetVersion.kind == RuleSetKind.rules, RuleSetVersion.name == name)
        .order_by(RuleSetVersion.version.desc())).scalars())


def validate_text(text: str) -> dict:
    """{valid, errors, rule_count}. Never raises for bad config."""
    try:
        config = parse_rule_set(text)
    except RuleSetError as exc:
        return {"valid": False, "errors": exc.errors, "rule_count": 0}
    return {"valid": True, "errors": [], "rule_count": len(config.rules)}


def _same_rules(a: str, b: str) -> bool:
    """True if both texts define the same rules (ignoring the version number and comments)."""
    dump = lambda t: parse_rule_set(t).model_dump(exclude={"version"})  # noqa: E731
    return dump(a) == dump(b)


def save_new_version(db: Session, user: User, text: str, reason: str, name: str = CORE_RULE_SET) -> RuleSetVersion:
    ensure_editor(user)
    if len(reason.strip()) < 5:
        raise HTTPException(status.HTTP_409_CONFLICT, "A reason (at least 5 characters) is required")
    current, _ = get_rule_set(db, name)
    new_version = max(v.version for v in versions(db, name)) + 1
    # The stored YAML carries its own version number; set it so the file and the DB agree.
    text = re.sub(r"(?m)^version:\s*\d+\s*$", f"version: {new_version}", text, count=1)
    check = validate_text(text)
    if not check["valid"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"message": "Invalid rules", "errors": check["errors"]})
    if parse_rule_set(text).name != name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Rule set name must stay '{name}'")
    if _same_rules(text, current.content_yaml):
        raise HTTPException(status.HTTP_409_CONFLICT, "No changes compared with the active version")

    current.is_active = False
    row = RuleSetVersion(kind=RuleSetKind.rules, name=name, version=new_version, content_yaml=text,
                         content_hash=_hash(text), is_active=True, created_by=user.id)
    db.add(row)
    db.flush()
    audit.log(db, user.id, "rules.updated", "rule_set", row.id, {
        "name": name, "from_version": current.version, "to_version": new_version,
        "content_hash": row.content_hash, "reason": reason.strip()})
    return row


def rerun_open_cases(db: Session, user: User) -> dict:
    """Re-run official validation on every open case with the active rules. Old runs are kept."""
    ensure_editor(user)
    row, _ = get_rule_set(db)
    apps = list(db.execute(select(Application).where(Application.status.in_(RERUN_STATUSES))).scalars())
    for app in apps:
        run_validation(db, user, app, precheck=False, skip_permission=True)
    audit.log(db, user.id, "rules.rerun", "rule_set", row.id,
              {"rule_set_version": version_label(row), "applications": len(apps)})
    return {"rule_set_version": version_label(row), "applications_rerun": len(apps)}
