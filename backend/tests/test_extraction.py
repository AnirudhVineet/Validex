import pytest
from sqlalchemy import select

from app.enums import DocumentStatus, ExtractionSource
from app.models import ApplicationDocument, ExtractedField
from app.models.base import new_id
from app.services import storage
from app.services.extraction import extract_document, words
from app.services.extraction.parse import normalize_date
from seed.docgen import DOC_TYPES

needs_ocr = pytest.mark.skipif(not words.ocr_available(), reason="Tesseract not installed (runs in Docker)")


def _store(db, users, pdf: bytes, doc_type: str) -> ApplicationDocument:
    from app.enums import ApplicationCategory, Role
    from app.models import Application

    applicant = users[Role.applicant]
    app = Application(institution_id=applicant.institution_id, category=ApplicationCategory.eoa_no_change,
                      academic_year="2027-28", created_by=applicant.id)
    db.add(app)
    db.flush()
    doc = ApplicationDocument(application_id=app.id, doc_type=doc_type, original_filename="t.pdf",
                              sha256=storage.sha256_hex(pdf), size_bytes=len(pdf), mime_type="application/pdf",
                              storage_path=storage.save_file(pdf, new_id(), ".pdf"),
                              uploaded_by=applicant.id)
    db.add(doc)
    db.flush()
    return doc


def _fields(db, doc) -> dict[str, ExtractedField]:
    rows = db.execute(select(ExtractedField).where(ExtractedField.document_id == doc.id)).scalars()
    return {f.field_name: f for f in rows}


@pytest.mark.parametrize("doc_type", DOC_TYPES)
def test_digital_pdf_fields_match_truth_with_page_and_bbox(db, users, make_pdf, doc_type):
    gen = make_pdf(doc_type)
    doc = extract_document(db, _store(db, users, gen.pdf, doc_type), "system")
    assert doc.status == DocumentStatus.extracted
    assert doc.classified_type == doc_type
    fields = _fields(db, doc)
    for name, expected in gen.truth.items():
        assert fields[name].value == expected, name
        assert fields[name].page == 1 or name in ("faculty_count", "faculty_ids")
        assert len(fields[name].bbox) == 4
        assert fields[name].source == ExtractionSource.pdf_text
        assert not fields[name].needs_confirmation


def test_missing_field_variant_omits_field(db, users, make_pdf):
    gen = make_pdf("fire_noc", "missing_field")
    fields = _fields(db, extract_document(db, _store(db, users, gen.pdf, "fire_noc"), "system"))
    assert "certificate_number" not in fields and "expiry_date" in fields


def test_scanned_without_ocr_fails_clearly(db, users, make_pdf, monkeypatch):
    monkeypatch.setattr("app.services.extraction.ocr_available", lambda: False)
    gen = make_pdf("fire_noc", "scanned")
    doc = extract_document(db, _store(db, users, gen.pdf, "fire_noc"), "system")
    assert doc.status == DocumentStatus.failed
    assert "Tesseract" in doc.extraction_error


def test_corrupt_pdf_marked_failed(db, users):
    doc = extract_document(db, _store(db, users, b"%PDF-1.4 not really a pdf", "fire_noc"), "system")
    assert doc.status == DocumentStatus.failed


@needs_ocr
def test_scanned_pdf_is_read_with_ocr(db, users, make_pdf):
    gen = make_pdf("fire_noc", "scanned")
    doc = extract_document(db, _store(db, users, gen.pdf, "fire_noc"), "system")
    assert doc.status == DocumentStatus.extracted and doc.extraction_method == "ocr"
    fields = _fields(db, doc)
    assert all(f.source == ExtractionSource.ocr for f in fields.values())
    assert fields["expiry_date"].value == gen.truth["expiry_date"]
    assert fields["certificate_number"].value == gen.truth["certificate_number"]


def test_normalize_date_formats():
    assert normalize_date("31-03-2025") == "2025-03-31"
    assert normalize_date("31 / 03 / 2025") == "2025-03-31"
    assert normalize_date("31 March 2025") == "2025-03-31"
    assert normalize_date("31-13-2025") is None


def test_certificate_number_strips_ocr_specks():
    from app.services.extraction.parse import _normalize_value

    assert _normalize_value("certificate_number", "FNOC-2026-140891.")[0] == "FNOC-2026-140891"
    assert _normalize_value("certificate_number", "-fnoc-2026-1 40891")[0] == "FNOC-2026-140891"
