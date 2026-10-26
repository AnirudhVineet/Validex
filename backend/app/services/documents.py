"""Document upload, supersede, field correction and file-link issuing.

Extraction runs synchronously inside the upload request (simple and deterministic for the
prototype; a few seconds for OCR). Move to a job queue for anything beyond a demo.
"""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import ExtractionSource, Role
from app.models import Application, ApplicationDocument, ExtractedField, User
from app.models.base import new_id, utcnow
from app.services import audit, storage
from app.services.analysis import analyze_file
from app.services.access import ensure_applicant_owner, ensure_editable, ensure_view, forbidden
from app.services.extraction import extract_document
from app.services.rules.loader import load_doc_types

IDENTIFIER_FIELDS = {"certificate_number", "faculty_ids"}
FIELD_CORRECTORS = {Role.scrutiny_officer, Role.senior_authority}


def upload_document(db: Session, user: User, app: Application, doc_type: str,
                    filename: str, data: bytes) -> ApplicationDocument:
    """Validate, store, supersede the previous file of the same type, then extract fields."""
    ensure_applicant_owner(user, app)
    ensure_editable(app)
    if doc_type not in load_doc_types():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown document type '{doc_type}'")
    try:
        mime, ext = storage.validate_upload(data)
    except storage.UploadRejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    previous = db.execute(select(ApplicationDocument).where(
        ApplicationDocument.application_id == app.id, ApplicationDocument.doc_type == doc_type,
        ApplicationDocument.is_current)).scalars().all()
    for old in previous:
        old.is_current = False
        audit.log(db, user.id, "document.superseded", "document", old.id, {"doc_type": doc_type})

    doc_id = new_id()
    doc = ApplicationDocument(
        id=doc_id, application_id=app.id, version=app.current_version, doc_type=doc_type,
        original_filename=filename[:255] or "upload", sha256=storage.sha256_hex(data),
        size_bytes=len(data), mime_type=mime, storage_path=storage.save_file(data, doc_id, ext),
        uploaded_by=user.id,
    )
    db.add(doc)
    db.flush()
    audit.log(db, user.id, "document.uploaded", "document", doc.id,
              {"application_id": app.id, "doc_type": doc_type, "sha256": doc.sha256,
               "size_bytes": doc.size_bytes, "mime_type": mime})
    extract_document(db, doc, user.id)
    analyze_document(db, doc, user.id)
    return doc


def analyze_document(db: Session, doc: ApplicationDocument, actor: str) -> None:
    """Upload-time signals (QR, page hashes, PDF metadata, signature, ELA). Audited as a summary."""
    doc.analysis = analyze_file(storage.full_path(doc.storage_path), doc.mime_type)
    pdf = doc.analysis.get("pdf") or {}
    audit.log(db, actor, "document.analyzed", "document", doc.id, {
        "qr_codes": len(doc.analysis.get("qr", [])),
        "incremental_updates": pdf.get("incremental_updates"),
        "signature_present": pdf.get("signature_present"),
        "ela_flag": (doc.analysis.get("ela") or {}).get("flag"),
        "errors": doc.analysis.get("errors", []),
    })


def get_fields(db: Session, doc: ApplicationDocument) -> list[ExtractedField]:
    return list(db.execute(select(ExtractedField).where(ExtractedField.document_id == doc.id)
                           .order_by(ExtractedField.field_name)).scalars())


def correct_field(db: Session, user: User, field: ExtractedField, value: str, reason: str) -> ExtractedField:
    """Officer correction. Keeps page/bbox; source becomes manual. Old and new values are audited."""
    if user.role not in FIELD_CORRECTORS:
        raise forbidden("Only scrutiny officers and senior authorities can correct fields")
    if len(reason.strip()) < 5:
        raise HTTPException(status.HTTP_409_CONFLICT, "A reason (at least 5 characters) is required")
    old = field.value
    masker = audit.mask if field.field_name in IDENTIFIER_FIELDS else (lambda v: v)
    field.value = value.strip()
    field.source = ExtractionSource.manual
    field.confidence = 1.0
    field.needs_confirmation = False
    field.corrected_by = user.id
    field.corrected_at = utcnow()
    audit.log(db, user.id, "field.corrected", "extracted_field", field.id,
              {"document_id": field.document_id, "field_name": field.field_name,
               "old_value": masker(old), "new_value": masker(field.value), "reason": reason.strip()})
    return field


def issue_file_link(db: Session, user: User, app: Application, doc: ApplicationDocument) -> str:
    ensure_view(user, app)
    token = storage.create_file_token(doc.id, user.id)
    audit.log(db, user.id, "document.link_issued", "document", doc.id, {})
    return token
