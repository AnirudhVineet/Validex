"""Load, validate and version rule sets and checklists.

YAML files in backend/config/ are the initial versions. On first use they are copied into
the `rule_set_versions` table; from then on the active DB version is used, and the rule
editor (Phase 2) creates new versions instead of editing in place.
"""
import hashlib
from pathlib import Path

import yaml
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR
from app.enums import RuleSetKind
from app.models import RuleSetVersion
from app.services.rules.checks import CHECKS
from app.services.rules.schema import ChecklistConfig, RuleSetConfig

CONFIG_DIR = BACKEND_DIR / "config"
RULES_DIR = CONFIG_DIR / "rules"
CHECKLISTS_DIR = CONFIG_DIR / "checklists"
CORE_RULE_SET = "core"


class RuleSetError(ValueError):
    """Raised when rule or checklist config is malformed. `errors` lists every problem."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Invalid configuration: " + "; ".join(errors))


def _load_yaml(text: str) -> dict:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RuleSetError([f"YAML syntax error: {exc}"]) from exc
    if not isinstance(data, dict):
        raise RuleSetError(["top level must be a mapping"])
    return data


def _pydantic_errors(exc: ValidationError) -> list[str]:
    return [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]


def parse_rule_set(text: str) -> RuleSetConfig:
    """Parse and fully validate rules YAML, including each check's params."""
    try:
        config = RuleSetConfig.model_validate(_load_yaml(text))
    except ValidationError as exc:
        raise RuleSetError(_pydantic_errors(exc)) from exc

    errors = []
    if not config.illustrative:
        errors.append("illustrative must be true until rules are checked against the official handbook")
    for rule in config.rules:
        entry = CHECKS.get(rule.condition.check)
        if entry is None:
            errors.append(f"{rule.id}: unknown check '{rule.condition.check}'")
            continue
        try:
            entry[1].model_validate(rule.condition.params)
        except ValidationError as exc:
            errors += [f"{rule.id}.params.{msg}" for msg in _pydantic_errors(exc)]
    if errors:
        raise RuleSetError(errors)
    return config


def parse_checklist(text: str) -> ChecklistConfig:
    try:
        return ChecklistConfig.model_validate(_load_yaml(text))
    except ValidationError as exc:
        raise RuleSetError(_pydantic_errors(exc)) from exc


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _active(db: Session, kind: RuleSetKind, name: str) -> RuleSetVersion | None:
    return db.execute(
        select(RuleSetVersion)
        .where(RuleSetVersion.kind == kind, RuleSetVersion.name == name, RuleSetVersion.is_active)
        .order_by(RuleSetVersion.version.desc())
    ).scalars().first()


def _seed_from_file(db: Session, kind: RuleSetKind, name: str, path: Path) -> RuleSetVersion:
    text = path.read_text(encoding="utf-8")
    config = parse_rule_set(text) if kind == RuleSetKind.rules else parse_checklist(text)
    row = RuleSetVersion(kind=kind, name=name, version=config.version, content_yaml=text,
                         content_hash=_hash(text), is_active=True)
    db.add(row)
    db.flush()
    return row


def get_rule_set(db: Session, name: str = CORE_RULE_SET) -> tuple[RuleSetVersion, RuleSetConfig]:
    """Active rule set (seeding it from YAML on first use)."""
    row = _active(db, RuleSetKind.rules, name) or _seed_from_file(
        db, RuleSetKind.rules, name, RULES_DIR / f"{name}.yaml")
    return row, parse_rule_set(row.content_yaml)


def get_checklist(db: Session, name: str) -> tuple[RuleSetVersion, ChecklistConfig]:
    """Active checklist for an application category (seeding it from YAML on first use)."""
    path = CHECKLISTS_DIR / f"{name}.yaml"
    row = _active(db, RuleSetKind.checklist, name)
    if row is None:
        if not path.exists():
            raise RuleSetError([f"no checklist configured for category '{name}'"])
        row = _seed_from_file(db, RuleSetKind.checklist, name, path)
    return row, parse_checklist(row.content_yaml)


def version_label(row: RuleSetVersion) -> str:
    return f"{row.name}@v{row.version}"


def load_doc_types() -> dict:
    """doc_type -> config (label, keywords, fields, ...). From config/doc_types.yaml."""
    data = _load_yaml((CONFIG_DIR / "doc_types.yaml").read_text(encoding="utf-8"))
    return data["doc_types"]
