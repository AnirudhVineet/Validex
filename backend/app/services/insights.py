"""Staff dashboards: expiry forecast, senior overview (status counts, ageing, common
deficiencies) and the time-saved estimate. All deterministic counts over existing data."""
from collections import Counter
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import ApplicationStatus, FindingStatus
from app.models import (
    Application, ApplicationDocument, ExtractedField, Finding, Institution, ValidationRun, VerificationRequest,
)
from app.models.base import utcnow
from app.services.applications import INSPECTION_DOC_TYPE
from app.services.dashboard import _status_counts
from app.services.rules.loader import get_rule_set
from app.services.validation import latest_run

OPEN_STATUSES = (ApplicationStatus.submitted, ApplicationStatus.under_scrutiny,
                 ApplicationStatus.escalated, ApplicationStatus.returned_for_correction)
AGE_BUCKETS = [(0, 7, "0-7 days"), (8, 14, "8-14 days"), (15, 30, "15-30 days"), (31, 10_000, "over 30 days")]


def expiry_forecast(db: Session, days: int, today: date | None = None) -> dict:
    """Current documents of submitted applications that expire within `days` (or already have)."""
    today = today or date.today()
    limit = today + timedelta(days=days)
    rows = db.execute(
        select(ExtractedField.value, ApplicationDocument, Application, Institution)
        .join(ApplicationDocument, ExtractedField.document_id == ApplicationDocument.id)
        .join(Application, ApplicationDocument.application_id == Application.id)
        .join(Institution, Application.institution_id == Institution.id)
        .where(ExtractedField.field_name == "expiry_date", ApplicationDocument.is_current,
               ApplicationDocument.doc_type != INSPECTION_DOC_TYPE, Application.submitted_at.is_not(None))
    ).all()
    items = []
    for value, doc, app, inst in rows:
        try:
            expiry = date.fromisoformat(value or "")
        except ValueError:
            continue
        if expiry <= limit:
            items.append({"application_id": app.id, "institution": inst.name, "doc_type": doc.doc_type,
                          "expiry_date": expiry.isoformat(), "days_left": (expiry - today).days,
                          "status": app.status.value})
    items.sort(key=lambda i: i["days_left"])
    return {"window_days": days, "today": today.isoformat(), "items": items,
            "expired": sum(1 for i in items if i["days_left"] < 0)}


def senior_overview(db: Session) -> dict:
    now = utcnow()
    open_apps = list(db.execute(select(Application).where(Application.status.in_(OPEN_STATUSES))).scalars())
    ageing = {label: 0 for _, _, label in AGE_BUCKETS}
    for app in open_apps:
        if app.submitted_at is None:
            continue
        age = (now - app.submitted_at).days
        for low, high, label in AGE_BUCKETS:
            if low <= age <= high:
                ageing[label] += 1

    rules = {r.id: r.description for r in get_rule_set(db)[1].rules}
    counter: Counter = Counter()
    for app in db.execute(select(Application).where(Application.submitted_at.is_not(None))).scalars():
        run = latest_run(db, app, include_precheck=False)
        if run is None:
            continue
        ids = {f.rule_id for f in db.execute(select(Finding).where(
            Finding.validation_run_id == run.id, Finding.status == FindingStatus.open)).scalars()}
        counter.update(ids)  # count applications affected, not findings
    common = [{"rule_id": rid, "description": rules.get(rid, rid), "applications": n}
              for rid, n in counter.most_common(8)]
    return {"status_counts": _status_counts(db), "ageing": ageing, "common_deficiencies": common,
            "open_applications": len(open_apps)}


def time_saved(db: Session) -> dict:
    """Estimated officer time saved. An ASSUMPTION-based estimate, not a measurement."""
    checked_docs = len(db.execute(
        select(ApplicationDocument.id).join(Application, ApplicationDocument.application_id == Application.id)
        .where(Application.submitted_at.is_not(None), ApplicationDocument.doc_type != INSPECTION_DOC_TYPE,
               ApplicationDocument.status == "extracted")).all())
    verifications = len(db.execute(select(VerificationRequest.id)).all())
    official_runs = len(db.execute(select(ValidationRun.id).where(ValidationRun.is_precheck.is_(False))).all())
    m_doc, m_ver, m_run = (settings.minutes_saved_per_document, settings.minutes_saved_per_verification,
                           settings.minutes_saved_per_run)
    minutes = checked_docs * m_doc + verifications * m_ver + official_runs * m_run
    return {
        "minutes": minutes, "hours": round(minutes / 60, 1),
        "inputs": {"documents_auto_checked": checked_docs, "issuer_verifications": verifications,
                   "official_validation_runs": official_runs},
        "assumption": (f"ASSUMPTION, not measured: {m_doc} min saved per document whose fields were read and "
                       f"checked automatically, {m_ver} min per issuer lookup, {m_run} min per validation run "
                       "(collating the checklist). Officers still review every finding. Replace these numbers "
                       "with timings from a real pilot."),
    }
