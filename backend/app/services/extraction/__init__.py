"""Document extraction service.

Pipeline: text layer (pdfplumber) -> if too little text, OCR (Tesseract) -> lines ->
classify document type -> labelled fields. Results are stored as ExtractedField rows with
page, bbox, confidence and source. If OCR is needed but unavailable, the document is marked
`failed` with a clear reason and validation records the affected checks as incomplete.
"""
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.enums import DocumentStatus, ExtractionSource
from app.models import ApplicationDocument, ExtractedField
from app.services import audit, storage
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


def extract_file(path, mime_type: str, doc_type: str) -> tuple[str, str | None, dict]:
    """Extract one file without touching the database: (method, classified_type, {field: ParsedField}).
    Raises ExtractionFailed when OCR is needed but unavailable. Used by the upload path and the evaluation."""
    doc_types = load_doc_types()
    words, method = _read_words(path, mime_type)
    lines = group_lines(words)
    parsed = extract_fields(lines, doc_types.get(doc_type, {}), from_ocr=(method == "ocr"))
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
        source = ExtractionSource.ocr if method == "ocr" else ExtractionSource.pdf_text
        for pf in parsed.values():
            db.add(ExtractedField(document_id=doc.id, field_name=pf.name, value=pf.value,
                                  confidence=pf.confidence, page=pf.page, bbox=pf.bbox,
                                  source=source, needs_confirmation=pf.needs_confirmation))
        doc.status, doc.extraction_method, doc.extraction_error = DocumentStatus.extracted, method, None

    db.flush()
    if doc.status == DocumentStatus.extracted:
        audit.log(db, actor, "document.extracted", "document", doc.id,
                  {"method": doc.extraction_method, "fields": len(parsed),
                   "classified_type": doc.classified_type})
    else:
        audit.log(db, actor, "document.extraction_failed", "document", doc.id,
                  {"reason": doc.extraction_error})
    return doc
