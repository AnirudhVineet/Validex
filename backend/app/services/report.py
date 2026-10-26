"""Structured validation report, filtered by role in the backend.

Applicants only ever receive findings with visible_to_applicant = True (never anomaly
indicators or internal-only checks). Staff see everything for official runs.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import Role, RuleSetKind, Severity
from app.models import Application, Finding, Institution, RuleSetVersion, User, ValidationRun
from app.services import priority
from app.services.access import STAFF, ensure_view
from app.services.applications import current_documents, missing_form_fields
from app.services.checklist import resolve_checklist
from app.services.documents import get_fields
from app.services.rules.loader import get_checklist, get_rule_set, load_doc_types, parse_rule_set
from app.services.verification import latest_verifications
from app.services.validation import latest_run

DISCLAIMER = ("Decision support only. Findings are automated pre-validation results for an "
              "authorised official to review; they are not an approval or rejection. Checklists "
              "and rules are ILLUSTRATIVE, not the official AICTE handbook.")
_SEVERITY_ORDER = {s: i for i, s in enumerate(Severity)}


def findings_for(db: Session, user: User, run: ValidationRun) -> list[Finding]:
    query = select(Finding).where(Finding.validation_run_id == run.id)
    if user.role == Role.applicant:
        query = query.where(Finding.visible_to_applicant.is_(True))
    findings = list(db.execute(query).scalars())
    return sorted(findings, key=lambda f: (_SEVERITY_ORDER[f.severity], f.rule_id))


def checklist_status(db: Session, app: Application) -> list[dict]:
    inst = db.get(Institution, app.institution_id)
    doc_types = load_doc_types()
    labels = {k: v.get("label", k) for k, v in doc_types.items()}
    _, cfg = get_checklist(db, app.category.value)
    docs = {d.doc_type: d for d in current_documents(db, app)}
    out = []
    for entry, item in zip(resolve_checklist(cfg, app, inst, labels), cfg.items):
        doc = docs.get(entry.doc_type)
        out.append({
            "doc_type": entry.doc_type, "label": entry.label, "description": item.description,
            "requirement": entry.requirement, "configured_as": entry.configured_as,
            "reason": entry.reason, "condition_unresolved": entry.condition_unresolved,
            "document_id": doc.id if doc else None,
            "document_status": doc.status.value if doc else None,
            "uploaded": doc is not None,
        })
    return out


def rules_info(db: Session, run: ValidationRun) -> dict:
    """Describe the rules of the rule-set version a run used (falls back to the active set)."""
    name, _, version = run.rule_set_version.partition("@v")
    row = db.execute(select(RuleSetVersion).where(
        RuleSetVersion.kind == RuleSetKind.rules, RuleSetVersion.name == name,
        RuleSetVersion.version == int(version or 0))).scalar_one_or_none()
    config = parse_rule_set(row.content_yaml) if row else get_rule_set(db)[1]
    return {r.id: {"description": r.description, "category": r.category, "check": r.condition.check}
            for r in config.rules}


def build_report(db: Session, user: User, app: Application, run_id: str | None = None) -> dict:
    ensure_view(user, app)
    is_applicant = user.role == Role.applicant
    if run_id:
        run = db.get(ValidationRun, run_id)
        if run is None or run.application_id != app.id or (run.is_precheck and not is_applicant):
            run = None
    else:
        run = latest_run(db, app, include_precheck=is_applicant)

    findings = findings_for(db, user, run) if run else []
    summary = {s.value: 0 for s in Severity}
    for f in findings:
        summary[f.severity.value] += 1

    documents = []
    for d in current_documents(db, app):
        documents.append({
            "id": d.id, "doc_type": d.doc_type, "original_filename": d.original_filename,
            "status": d.status.value, "sha256": d.sha256, "uploaded_at": d.uploaded_at,
            "classified_type": d.classified_type, "extraction_method": d.extraction_method,
            "extraction_error": d.extraction_error, "fields": get_fields(db, d),
        })

    staff = user.role in STAFF
    verifications = []
    if staff:
        types = {d["id"]: d["doc_type"] for d in documents}
        for v in latest_verifications(db, app).values():
            if v.document_id in types:
                verifications.append({**{c: getattr(v, c) for c in (
                    "id", "document_id", "source", "is_mock", "reference_submitted", "requested_at", "status",
                    "submitted_values", "source_values", "mismatches", "error")}, "doc_type": types[v.document_id]})

    return {
        "rules": rules_info(db, run) if run else {},
        "verifications": verifications,
        "priority": priority.compute(db, app) if staff else None,
        "application": app,
        "institution": db.get(Institution, app.institution_id),
        "run": run,
        "summary": summary,
        "findings": findings,
        "incomplete_checks": run.incomplete_checks if run else [],
        "checklist": checklist_status(db, app),
        "missing_form_fields": missing_form_fields(db, app),
        "documents": documents,
        "disclaimer": DISCLAIMER,
    }
