"""Document extraction service.

Pipeline: text layer (pdfplumber) -> if too little text, OCR (Tesseract) -> lines ->
classify document type -> labelled fields. Results are stored as ExtractedField rows with
page, bbox, confidence and source. If OCR is needed but unavailable, the document is marked
`failed` with a clear reason and validation records the affected checks as incomplete.
"""
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import DocumentStatus, ExtractionSource
from app.models import ApplicationDocument, ExtractedField
from app.services import audit, storage
from app.services.extraction import ai_reader
from app.services.extraction.parse import classify, extract_fields, group_lines
from app.services.extraction.words import ocr_available, ocr_image_words, ocr_pdf_words, pdf_text_words
from app.services.rules.loader import load_doc_types

# A PDF with fewer text-layer words than this is treated as a scan.
MIN_TEXT_WORDS = 15


class ExtractionFailed(Exception):
    pass


def _read_words(path, mime_type: str):
    """Return (words, method) where method is 'pdf_text' or 'ocr'."""
    if mime_type == "application/pdf":
        words, _ = pdf_text_words(path)
        if len(words) >= MIN_TEXT_WORDS:
            return words, "pdf_text"
        if not ocr_available():
            raise ExtractionFailed("Scanned PDF needs OCR, but the OCR engine (Tesseract) is not "
                                   "installed on this server. Manual review needed.")
        return ocr_pdf_words(path), "ocr"
    if not ocr_available():
        raise ExtractionFailed("Image upload needs OCR, but the OCR engine (Tesseract) is not "
                               "installed on this server. Manual review needed.")
    return ocr_image_words(path), "ocr"


def extract_file(path, mime_type: str, doc_type: str, ai_caller=None) -> tuple[str, str | None, dict]:
    """Extract one file without touching the database: (method, classified_type, {field: ParsedField}).

    Scans go through OCR; if OCR misses fields, is unsure, or is not installed, and the AI fallback is
    enabled, the Groq vision model suggests values (source ai_vision, always needs confirmation).
    Raises ExtractionFailed when nothing could read the document."""
    doc_types = load_doc_types()
    cfg = doc_types.get(doc_type, {})
    try:
        words, method = _read_words(path, mime_type)
    except ExtractionFailed:
        if not settings.ai_fallback_enabled:
            raise
        words, method = [], "none"  # OCR unavailable: let the AI reader try
    lines = group_lines(words)
    parsed = extract_fields(lines, cfg, from_ocr=(method == "ocr")) if words else {}

    if method in ("ocr", "none") and settings.ai_fallback_enabled and ai_reader.needs_help(parsed, cfg):
        try:
            values = ai_reader.read_page(path, mime_type, cfg.get("label", doc_type),
                                         ai_reader.wanted_fields(cfg), caller=ai_caller)
        except ai_reader.LLMUnavailable as exc:
            if method == "none":
                raise ExtractionFailed(f"OCR is not installed and the AI fallback reader is unavailable "
                                       f"({exc}). Manual review needed.") from exc
        else:
            if ai_reader.merge(parsed, values, lines):
                method = "ocr+ai_vision" if method == "ocr" else "ai_vision"
    if method == "none":
        raise ExtractionFailed("Neither OCR nor the AI fallback reader could read this document. Manual review needed.")
    return method, classify(lines, doc_types), parsed


def extract_document(db: Session, doc: ApplicationDocument, actor: str) -> ApplicationDocument:
    """Extract fields for one document, replacing earlier extracted fields. Caller commits."""
    doc.status = DocumentStatus.processing
    db.execute(delete(ExtractedField).where(ExtractedField.document_id == doc.id))
    try:
        method, doc.classified_type, parsed = extract_file(storage.full_path(doc.storage_path),
                                                           doc.mime_type, doc.doc_type)
    except ExtractionFailed as exc:
        doc.status, doc.extraction_error = DocumentStatus.failed, str(exc)
    except Exception as exc:  # noqa: BLE001 - a broken file must not crash the upload
        doc.status = DocumentStatus.failed
        doc.extraction_error = f"Could not read document ({type(exc).__name__}). Manual review needed."
    else:
        source = ExtractionSource.pdf_text if method == "pdf_text" else ExtractionSource.ocr
        for pf in parsed.values():
            db.add(ExtractedField(document_id=doc.id, field_name=pf.name, value=pf.value,
                                  confidence=pf.confidence, page=pf.page, bbox=pf.bbox,
                                  source=ExtractionSource(pf.source) if pf.source else source,
                                  needs_confirmation=pf.needs_confirmation))
        doc.status, doc.extraction_method, doc.extraction_error = DocumentStatus.extracted, method, None

    db.flush()
    if doc.status == DocumentStatus.extracted:
        audit.log(db, actor, "document.extracted", "document", doc.id,
                  {"method": doc.extraction_method, "fields": len(parsed),
                   "ai_suggested_fields": sorted(n for n, pf in parsed.items() if pf.source == "ai_vision"),
                   "ai_model": settings.vision_model if "ai_vision" in (doc.extraction_method or "") else None,
                   "classified_type": doc.classified_type})
    else:
        audit.log(db, actor, "document.extraction_failed", "document", doc.id,
                  {"reason": doc.extraction_error})
    return doc
