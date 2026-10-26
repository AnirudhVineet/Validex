"""Minimal inspector workflow and infrastructure advisory.

Inspectors see escalated (flagged) cases, add notes and upload evidence photos / PDFs with a
declared label. The advisory only reports whether evidence is PRESENT for each illustrative
item and which keywords could be read from it. It never measures areas, counts seats or
judges adequacy.
"""
import re

import yaml
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import DocumentStatus, Role
from app.models import Application, ApplicationDocument, InspectionRecord, User
from app.models.base import new_id
from app.services import audit, storage
from app.services.access import ensure_view, forbidden
from app.services.applications import INSPECTION_DOC_TYPE
from app.services.extraction.words import ocr_available, ocr_image_words, ocr_pdf_words, pdf_text_words
from app.services.rules.loader import CONFIG_DIR

ADVISORY_NOTICE = ("Advisory only: shows whether inspection evidence is present for each ILLUSTRATIVE item and "
                   "which labels could be read from it. No area measurement, seat counting or adequacy judgement.")


def infrastructure_items() -> list[dict]:
    data = yaml.safe_load((CONFIG_DIR / "infrastructure.yaml").read_text(encoding="utf-8"))
    return data["items"]


def _readable_text(doc: ApplicationDocument) -> str:
    """Best-effort text from evidence for keyword labels. Empty when OCR is unavailable."""
    path = storage.full_path(doc.storage_path)
    try:
        if doc.mime_type == "application/pdf":
            words, _ = pdf_text_words(path)
            if not words and ocr_available():
                words = ocr_pdf_words(path)
        elif ocr_available():
            words = ocr_image_words(path)
        else:
            words = []
    except Exception:  # noqa: BLE001 - unreadable evidence just has no labels
        words = []
    return " ".join(w.text for w in words).lower()


def add_inspection(db: Session, user: User, app: Application, notes: str, label: str | None,
                   filename: str | None, data: bytes | None) -> InspectionRecord:
    if user.role != Role.inspector:
        raise forbidden("Only inspectors can add inspection records")
    ensure_view(user, app)  # inspectors see escalated (flagged) cases only
    if not notes.strip() and not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Add notes or an evidence file")
    labels = {i["key"] for i in infrastructure_items()}
    if data and label not in labels:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Evidence label must be one of {sorted(labels)}")

    doc = None
    if data:
        try:
            mime, ext = storage.validate_upload(data)
        except storage.UploadRejected as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        doc_id = new_id()
        doc = ApplicationDocument(
            id=doc_id, application_id=app.id, version=app.current_version, doc_type=INSPECTION_DOC_TYPE,
            original_filename=(filename or "evidence")[:255], sha256=storage.sha256_hex(data), size_bytes=len(data),
            mime_type=mime, storage_path=storage.save_file(data, doc_id, ext), status=DocumentStatus.uploaded,
            uploaded_by=user.id, analysis={"evidence_label": label})
        db.add(doc)
        db.flush()
    record = InspectionRecord(application_id=app.id, inspector_id=user.id, notes=notes.strip(),
                              evidence_document_id=doc.id if doc else None, evidence_label=label if doc else None)
    db.add(record)
    db.flush()
    audit.log(db, user.id, "inspection.recorded", "application", app.id, {
        "inspection_id": record.id, "evidence_label": record.evidence_label,
        "evidence_sha256": doc.sha256 if doc else None, "has_notes": bool(notes.strip())})
    return record


def records(db: Session, app: Application) -> list[InspectionRecord]:
    return list(db.execute(select(InspectionRecord).where(InspectionRecord.application_id == app.id)
                           .order_by(InspectionRecord.created_at)).scalars())


def advisory(db: Session, app: Application) -> dict:
    evidence = [r for r in records(db, app) if r.evidence_document_id]
    docs = {r.evidence_document_id: db.get(ApplicationDocument, r.evidence_document_id) for r in evidence}
    texts = {doc_id: _readable_text(doc) for doc_id, doc in docs.items() if doc}
    items = []
    for item in infrastructure_items():
        files = [r for r in evidence if r.evidence_label == item["key"]]
        keywords = [k for k in item.get("keywords", [])
                    if any(re.search(rf"\b{re.escape(k)}\b", t) for t in texts.values())]
        items.append({"key": item["key"], "label": item["label"], "evidence_files": len(files),
                      "present": bool(files), "labels_read_from_evidence": keywords})
    return {"notice": ADVISORY_NOTICE, "illustrative": True, "items": items,
            "ocr_available": ocr_available()}
