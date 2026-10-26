"""Run validation for an application and store the results as a ValidationRun + Findings.

Everything here is deterministic: checklist resolution, rule evaluation, statuses.
Old runs and their findings are kept for audit; a re-run creates a new run.
"""
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import ApplicationStatus, ExtractionSource, FindingStatus, Role
from app.models import Application, ExtractedField, Finding, Institution, User, ValidationRun
from app.models.base import utcnow
from app.services import audit
from app.services.access import EDITABLE, REVIEWERS, ensure_applicant_owner, forbidden
from app.services.applications import current_documents
from app.services.checklist import resolve_checklist
from app.services.rules.context import DocView, FieldView, InstitutionView, ValidationContext, VerificationView
from app.services.rules.evaluator import evaluate
from app.services.rules.loader import get_checklist, get_rule_set, load_doc_types, version_label
from app.services.crossapp import find_matches
from app.services.verification import latest_verifications

OFFICIAL_RUN_STATUSES = {ApplicationStatus.submitted, ApplicationStatus.under_scrutiny,
                         ApplicationStatus.escalated}


def build_context(db: Session, app: Application, today: date) -> tuple[ValidationContext, str]:
    """Collect everything the checks need. Returns (context, checklist version label)."""
    inst = db.get(Institution, app.institution_id)
    doc_types = load_doc_types()
    labels = {k: v.get("label", k) for k, v in doc_types.items()}
    checklist_row, checklist_cfg = get_checklist(db, app.category.value)

    docs: dict[str, DocView] = {}
    current = current_documents(db, app)
    for d in current:
        fields = list(db.execute(select(ExtractedField).where(ExtractedField.document_id == d.id)).scalars())
        docs[d.doc_type] = DocView(
            id=d.id, doc_type=d.doc_type, status=d.status.value, classified_type=d.classified_type,
            extraction_error=d.extraction_error, sha256=d.sha256, analysis=d.analysis or {},
            ai_pending={f.field_name: FieldView(f.field_name, f.value, f.confidence, f.page, f.bbox,
                                                f.source.value, True)
                        for f in fields if f.source == ExtractionSource.ai_vision},
            fields={f.field_name: FieldView(f.field_name, f.value, f.confidence, f.page, f.bbox,
                                            f.source.value, f.needs_confirmation)
                    for f in fields if f.source != ExtractionSource.ai_vision},
        )
    ctx = ValidationContext(
        institution=InstitutionView(inst.name, inst.address, inst.approved_intake, inst.faculty_count,
                                    inst.deficiency_status, inst.ter_payment_status),
        documents=docs,
        checklist=resolve_checklist(checklist_cfg, app, inst, labels),
        today=today,
        doc_labels=labels,
        verifications={doc_id: VerificationView(v.status.value, v.source, v.is_mock, v.reference_submitted,
                                                v.mismatches or [], v.error)
                       for doc_id, v in latest_verifications(db, app).items()},
        cross_matches=find_matches(db, app, current),
    )
    return ctx, version_label(checklist_row)


def _check_permission(user: User, app: Application, precheck: bool) -> None:
    if precheck:
        ensure_applicant_owner(user, app)
        if app.status not in EDITABLE:
            raise HTTPException(status.HTTP_409_CONFLICT, "Pre-check is only available before submission")
    else:
        if user.role not in REVIEWERS and user.role != Role.applicant:
            raise forbidden("Not allowed to run validation")
        if user.role == Role.applicant:
            raise forbidden("Applicants run pre-checks; official validation runs on submission")
        if app.status not in OFFICIAL_RUN_STATUSES:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"Official validation is not available while '{app.status.value}'")


def run_validation(db: Session, user: User, app: Application, precheck: bool,
                   today: date | None = None, skip_permission: bool = False) -> ValidationRun:
    """Evaluate the active rule set and store a new run with its findings. Caller commits."""
    if not skip_permission:
        _check_permission(user, app, precheck)
    today = today or date.today()
    rules_row, rule_set = get_rule_set(db)
    ctx, checklist_version = build_context(db, app, today)

    previous = None if precheck else latest_run(db, app, include_precheck=False)
    reviewed = _reviewed_findings(db, previous)

    run = ValidationRun(application_id=app.id, application_version=app.current_version,
                        rule_set_version=version_label(rules_row), checklist_version=checklist_version,
                        is_precheck=precheck, started_by=user.id)
    db.add(run)
    db.flush()
    result = evaluate(ctx, rule_set)
    for rf in result.findings:
        d = rf.draft
        finding = Finding(
            application_id=app.id, document_id=d.document_id, validation_run_id=run.id,
            rule_id=rf.rule.id, rule_version=str(rf.rule.version), category=rf.rule.category,
            severity=rf.rule.severity, title=d.title, found_value=d.found_value,
            expected_value=d.expected_value, evidence=d.evidence, explanation=d.explanation,
            suggested_action=rf.rule.recommended_action, visible_to_applicant=rf.visible_to_applicant,
        )
        earlier = reviewed.get((finding.rule_id, finding.document_id, finding.found_value))
        if earlier is not None:
            finding.status, finding.reviewed_by = earlier.status, earlier.reviewed_by
            reason = earlier.review_reason or ""
            finding.review_reason = reason if reason.startswith("(carried over") else f"(carried over from run {previous.id[:8]}) {reason}"
        db.add(finding)
    run.incomplete_checks = result.incomplete
    run.status = "completed"
    run.finished_at = utcnow()
    db.flush()
    audit.log(db, user.id, "validation.run", "application", app.id, {
        "run_id": run.id, "precheck": precheck, "rule_set_version": run.rule_set_version,
        "checklist_version": checklist_version, "findings": len(result.findings),
        "incomplete_checks": len(result.incomplete), "today": today.isoformat(),
    })
    from app.services import alerts  # local import: alerts reads verification + finding tables

    alerts.after_validation(db, app, run)
    return run


def _reviewed_findings(db: Session, run: ValidationRun | None) -> dict[tuple, Finding]:
    """Reviewed findings of a previous official run, keyed so identical findings keep their review."""
    if run is None:
        return {}
    rows = db.execute(select(Finding).where(Finding.validation_run_id == run.id,
                                            Finding.status != FindingStatus.open)).scalars()
    return {(f.rule_id, f.document_id, f.found_value): f for f in rows}


def latest_run(db: Session, app: Application, include_precheck: bool) -> ValidationRun | None:
    query = select(ValidationRun).where(ValidationRun.application_id == app.id)
    if not include_precheck:
        query = query.where(ValidationRun.is_precheck.is_(False))
    return db.execute(query.order_by(ValidationRun.started_at.desc(), ValidationRun.id.desc())).scalars().first()
