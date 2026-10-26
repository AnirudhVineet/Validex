"""AI fallback reader (Groq vision) and the optional summary client. No real API calls: the model call is stubbed."""
import pytest
from sqlalchemy import select

from app.config import settings
from app.enums import Role
from app.models import AuditEvent, ExtractedField
from app.services import llm
from app.services.extraction import ExtractionFailed, ai_reader, extract_file
from app.services.extraction.parse import Line, ParsedField
from app.services.extraction.words import Word
from tests.helpers import create_app, report, rule_ids, upload, upload_set


@pytest.fixture()
def no_ocr(monkeypatch):
    monkeypatch.setattr("app.services.extraction.ocr_available", lambda: False)


@pytest.fixture()
def ai_on(monkeypatch):
    monkeypatch.setattr(settings, "ai_fallback_enabled", True)


def fake_reader(values):
    return lambda path, mime, label, fields, caller=None: {f: values.get(f) for f in fields}


def test_disabled_by_default_scan_without_ocr_fails(tmp_path, make_pdf, no_ocr):
    assert settings.ai_fallback_enabled is False
    path = tmp_path / "scan.pdf"
    path.write_bytes(make_pdf("fire_noc", "scanned").pdf)
    with pytest.raises(ExtractionFailed, match="Tesseract"):
        extract_file(path, "application/pdf", "fire_noc")


def test_ai_reads_scan_when_ocr_missing(tmp_path, make_pdf, no_ocr, ai_on, monkeypatch):
    gen = make_pdf("fire_noc", "scanned")
    path = tmp_path / "scan.pdf"
    path.write_bytes(gen.pdf)
    t = gen.truth
    printed = {"certificate_number": t["certificate_number"] + ".", "institution_name": t["institution_name"],
               "issue_date": "-".join(reversed(t["issue_date"].split("-"))), "expiry_date": None,
               "issuing_authority": t["issuing_authority"], "address": t["address"]}
    monkeypatch.setattr(ai_reader, "read_page", fake_reader(printed))
    method, _, parsed = extract_file(path, "application/pdf", "fire_noc")
    assert method == "ai_vision"
    assert parsed["certificate_number"].value == t["certificate_number"]  # normalised like OCR values
    assert parsed["issue_date"].value == t["issue_date"]                  # dd-mm-yyyy -> ISO
    assert "expiry_date" not in parsed                                     # null stays missing, never guessed
    assert all(pf.source == "ai_vision" and pf.needs_confirmation and pf.confidence == 0.6 for pf in parsed.values())


def test_ai_unavailable_without_ocr_is_a_clear_failure(tmp_path, make_pdf, no_ocr, ai_on, monkeypatch):
    path = tmp_path / "scan.pdf"
    path.write_bytes(make_pdf("fire_noc", "scanned").pdf)

    def down(*_, **__):
        raise llm.LLMUnavailable("GROQ_API_KEY is not set")

    monkeypatch.setattr(ai_reader, "read_page", down)
    with pytest.raises(ExtractionFailed, match="AI fallback reader is unavailable"):
        extract_file(path, "application/pdf", "fire_noc")


def test_digital_pdfs_never_call_the_ai(tmp_path, make_pdf, ai_on, monkeypatch):
    def boom(*_, **__):
        raise AssertionError("AI must not be called for digital PDFs")

    monkeypatch.setattr(ai_reader, "read_page", boom)
    path = tmp_path / "digital.pdf"
    path.write_bytes(make_pdf("fire_noc").pdf)
    method, _, _ = extract_file(path, "application/pdf", "fire_noc")
    assert method == "pdf_text"


def test_merge_keeps_confident_ocr_and_locates_bbox():
    words = [Word("Valid", 10, 100, 40, 110, 1, 0.9, (1, 1, 1)), Word("Until:", 42, 100, 70, 110, 1, 0.9, (1, 1, 1)),
             Word("31-03-2029", 72, 100, 130, 110, 1, 0.5, (1, 1, 1))]
    lines = [Line(words)]
    parsed = {"institution_name": ParsedField("institution_name", "OCR NAME", 0.95, 1, [0, 0, 1, 1], False),
              "expiry_date": ParsedField("expiry_date", "31-O3-2O29", 0.4, 1, [72, 100, 130, 110], True)}
    added = ai_reader.merge(parsed, {"institution_name": "AI NAME", "expiry_date": "31-03-2029",
                                     "certificate_number": None}, lines)
    assert added == 1
    assert parsed["institution_name"].value == "OCR NAME"                 # confident OCR wins
    assert parsed["expiry_date"].value == "2029-03-31" and parsed["expiry_date"].source == "ai_vision"
    assert parsed["expiry_date"].bbox == [10.0, 100.0, 130.0, 110.0]      # found in the OCR line
    assert "certificate_number" not in parsed


def test_rules_ignore_ai_values_until_officer_confirms(client, auth_header, make_pdf, no_ocr, ai_on, monkeypatch, db):
    gen = make_pdf("fire_noc", "expired")  # digital, but we pretend it is a scan read only by the AI
    scan = make_pdf("fire_noc", "scanned", seed=5)
    t = gen.truth
    monkeypatch.setattr(ai_reader, "read_page", fake_reader({
        "certificate_number": scan.truth["certificate_number"], "institution_name": t["institution_name"],
        "issue_date": t["issue_date"], "expiry_date": t["expiry_date"], "issuing_authority": t["issuing_authority"],
        "address": t["address"]}))
    applicant, officer = auth_header(Role.applicant), auth_header(Role.scrutiny_officer)
    app = create_app(client, applicant)
    upload_set(client, applicant, app["id"], make_pdf, skip=("fire_noc",))
    assert upload(client, applicant, app["id"], "fire_noc", scan.pdf).json()["extraction_method"] == "ai_vision"
    client.post(f"/api/applications/{app['id']}/submit", headers=applicant)
    client.post(f"/api/applications/{app['id']}/start-scrutiny", headers=officer)

    rep = report(client, officer, app["id"])
    ids = rule_ids(rep)
    assert "EXP-001" not in ids and "COMP-002" not in ids                 # AI value not used by any rule
    assert "EXT-001" in ids                                                # "confirm AI-read ..." for the officer
    assert any("awaits officer confirmation" in c["reason"] for c in rep["incomplete_checks"])
    assert not any(f["rule_id"] == "EXT-001" for f in report(client, applicant, app["id"])["findings"])

    expiry = db.execute(select(ExtractedField).where(ExtractedField.field_name == "expiry_date",
                                                     ExtractedField.source == "ai_vision")).scalar_one()
    res = client.patch(f"/api/fields/{expiry.id}", headers=officer,
                       json={"value": expiry.value, "reason": "Checked against the document image"})
    assert res.json()["source"] == "manual"
    assert db.execute(select(AuditEvent).where(AuditEvent.event_type == "field.confirmed")).scalars().first()
    client.post(f"/api/applications/{app['id']}/validate", headers=officer)
    assert "EXP-001" in rule_ids(report(client, officer, app["id"]))      # now a confirmed value, rule applies


def test_llm_client_without_key(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    with pytest.raises(llm.LLMUnavailable, match="GROQ_API_KEY"):
        llm.chat_json("m", "s", "u", "x", {"type": "object"})


def test_summary_uses_groq_settings(client, auth_header, make_pdf, monkeypatch):
    from app.services import summary
    from tests.helpers import submitted_under_scrutiny

    app_id, _, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "expired"})
    monkeypatch.setattr(settings, "llm_summary_enabled", True)
    monkeypatch.setattr(settings, "groq_api_key", "")  # real client path -> clear "unavailable" note
    res = client.post(f"/api/applications/{app_id}/summary", headers=officer).json()
    assert res["model"] == settings.summary_model and "GROQ_API_KEY" in res["note"]
    calls = {}

    def fake(model, system, content, name, schema, timeout=60.0):
        calls["model"] = model
        return {"insufficient_evidence": True, "points": []}

    monkeypatch.setattr(summary, "chat_json", fake)
    client.post(f"/api/applications/{app_id}/summary", headers=officer)
    assert calls["model"] == "openai/gpt-oss-120b"
