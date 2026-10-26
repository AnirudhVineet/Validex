"""Issuer verification gateway (all sources are MOCK in this prototype).

For each document with a known issuer: take the reference from the QR code (preferred) or the
extracted certificate number, ask the connector, and compare submitted values with the
issuer's values. Statuses:

  verified            record found, values match, not expired at source
  mismatch            record found, at least one value differs
  expired             record found, values match, source expiry is before today
  pending             source says the record is still being processed
  source_unavailable  connector timed out / unreachable  -> needs manual review
  manual_review       no reference, reference unknown at source, or nothing to compare

Never invents a result. Every request is stored and audited.
"""
from datetime import date

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import VerificationStatus
from app.models import Application, ApplicationDocument, ExtractedField, VerificationRequest
from app.services import audit
from app.services.rules.checks import normalize_text
from app.services.verification.connectors import ISSUER_FOR_DOC_TYPE, SourceUnavailable, get_connector

COMPARED_FIELDS = ("institution_name", "certificate_number", "issue_date", "expiry_date")
NAME_MATCH_THRESHOLD = 90


def _submitted_values(db: Session, doc: ApplicationDocument) -> dict:
    rows = db.execute(select(ExtractedField).where(ExtractedField.document_id == doc.id)).scalars()
    return {f.field_name: f.value for f in rows if f.field_name in COMPARED_FIELDS and f.value}


def _reference(doc: ApplicationDocument, submitted: dict) -> tuple[str | None, str]:
    for q in (doc.analysis or {}).get("qr", []):
        if q.get("ref"):
            return q["ref"], "qr"
    if submitted.get("certificate_number"):
        return submitted["certificate_number"], "certificate_number"
    return None, "none"


def compare(submitted: dict, source: dict) -> list[dict]:
    """Field-by-field comparison. Names use fuzzy matching; numbers and dates must be exact."""
    mismatches = []
    for name in COMPARED_FIELDS:
        if name not in submitted or name not in source:
            continue
        a, b = str(submitted[name]), str(source[name])
        if name == "institution_name":
            same = fuzz.token_sort_ratio(normalize_text(a), normalize_text(b)) >= NAME_MATCH_THRESHOLD
        else:
            same = a.replace(" ", "").upper() == b.replace(" ", "").upper()
        if not same:
            mismatches.append({"field": name, "submitted": a, "source": b})
    return mismatches


def _decide(record: dict, submitted: dict, today: date) -> tuple[VerificationStatus, list[dict], str | None]:
    if record.get("status") == "pending":
        return VerificationStatus.pending, [], None
    if not submitted:
        return VerificationStatus.manual_review, [], "No extracted values to compare with the issuer record"
    mismatches = compare(submitted, record)
    if mismatches:
        return VerificationStatus.mismatch, mismatches, None
    expiry = record.get("expiry_date")
    if expiry and date.fromisoformat(expiry) < today:
        return VerificationStatus.expired, [], None
    return VerificationStatus.verified, [], None


def verify_document(db: Session, doc: ApplicationDocument, actor: str,
                    today: date | None = None) -> VerificationRequest | None:
    """Verify one document. Returns None when its type has no issuer. Caller commits."""
    issuer_code = ISSUER_FOR_DOC_TYPE.get(doc.doc_type)
    if issuer_code is None:
        return None
    today = today or date.today()
    connector = get_connector(issuer_code)
    submitted = _submitted_values(db, doc)
    reference, ref_source = _reference(doc, submitted)

    req = VerificationRequest(application_id=doc.application_id, document_id=doc.id,
                              source=connector.label, is_mock=connector.is_mock,
                              reference_submitted=reference or "", submitted_values=submitted,
                              source_values={}, mismatches=[])
    if reference is None:
        req.status = VerificationStatus.manual_review
        req.error = "No reference found (no readable QR code or certificate number)"
    else:
        try:
            record = connector.lookup(reference)
        except SourceUnavailable as exc:
            req.status, req.error = VerificationStatus.source_unavailable, str(exc)
        else:
            if record is None:
                req.status = VerificationStatus.manual_review
                req.error = f"Reference not found at {connector.label}"
            else:
                req.source_values = {k: record[k] for k in COMPARED_FIELDS if k in record}
                req.status, req.mismatches, req.error = _decide(record, submitted, today)

    db.add(req)
    db.flush()
    audit.log(db, actor, "verification.completed", "document", doc.id, {
        "application_id": doc.application_id, "source": req.source, "is_mock": req.is_mock,
        "reference": audit.mask(reference), "reference_from": ref_source, "status": req.status.value,
        "mismatch_fields": [m["field"] for m in req.mismatches], "error": req.error,
    })
    return req


def verify_application(db: Session, app: Application, actor: str,
                       today: date | None = None) -> list[VerificationRequest]:
    from app.services.applications import current_documents

    results = [verify_document(db, d, actor, today) for d in current_documents(db, app)]
    return [r for r in results if r is not None]


def latest_verifications(db: Session, app: Application) -> dict[str, VerificationRequest]:
    """Most recent verification per document id."""
    rows = db.execute(select(VerificationRequest).where(VerificationRequest.application_id == app.id)
                      .order_by(VerificationRequest.requested_at)).scalars()
    return {r.document_id: r for r in rows}
