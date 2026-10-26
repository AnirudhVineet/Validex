"""MOCK issuer gateway: all six statuses, never inventing a result."""
import json

from sqlalchemy import select

from app.config import settings
from app.enums import Role
from app.models import AuditEvent
from tests.conftest import register_issuer_record
from tests.helpers import create_app, report, rule_ids, submitted_under_scrutiny, upload


def _verifications(client, headers, app_id) -> dict:
    res = client.get(f"/api/applications/{app_id}/verifications", headers=headers)
    assert res.status_code == 200, res.text
    return {v["doc_type"]: v for v in res.json()}


def test_verified_on_submit(client, auth_header, make_pdf):
    app_id, _, officer = submitted_under_scrutiny(client, auth_header, make_pdf)
    v = _verifications(client, officer, app_id)
    assert set(v) == {"fire_noc", "land_document"}  # affidavit / faculty list have no issuer
    assert all(x["status"] == "verified" and x["is_mock"] for x in v.values())
    assert v["fire_noc"]["source_values"]["certificate_number"] == v["fire_noc"]["reference_submitted"]


def test_mismatch_for_altered_expiry(client, auth_header, make_pdf):
    app_id, _, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "altered"})
    v = _verifications(client, officer, app_id)["fire_noc"]
    assert v["status"] == "mismatch"
    assert v["mismatches"][0]["field"] == "expiry_date"
    assert v["mismatches"][0]["submitted"] != v["mismatches"][0]["source"]
    assert {"VER-001", "ANO-003"} <= rule_ids(report(client, officer, app_id))


def test_expired_at_source(client, auth_header, make_pdf):
    app_id, _, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "expired"})
    assert _verifications(client, officer, app_id)["fire_noc"]["status"] == "expired"


def _with_record_change(make_pdf, doc_type, **changes):
    gen = make_pdf(doc_type)
    register_issuer_record(gen, **changes)
    return gen


def _submit_with(client, auth_header, docs: dict):
    applicant, officer = auth_header(Role.applicant), auth_header(Role.scrutiny_officer)
    app = create_app(client, applicant)
    for doc_type, gen in docs.items():
        assert upload(client, applicant, app["id"], doc_type, gen.pdf).status_code == 201
    client.post(f"/api/applications/{app['id']}/submit", headers=applicant)
    return app["id"], officer


def test_pending_and_timeout_and_not_found(client, auth_header, make_pdf):
    docs = {"fire_noc": _with_record_change(make_pdf, "fire_noc", status="pending"),
            "land_document": _with_record_change(make_pdf, "land_document", simulate="timeout"),
            "accreditation_certificate": make_pdf("accreditation_certificate")}
    # Remove the accreditation record: the issuer does not know this reference.
    data = json.loads(settings.mock_issuer_data_path.read_text())
    data["records"].pop(docs["accreditation_certificate"].qr_ref)
    settings.mock_issuer_data_path.write_text(json.dumps(data))

    app_id, officer = _submit_with(client, auth_header, docs)
    v = _verifications(client, officer, app_id)
    assert v["fire_noc"]["status"] == "pending"
    assert v["land_document"]["status"] == "source_unavailable"
    assert "timeout" in v["land_document"]["error"] and v["land_document"]["source_values"] == {}
    assert v["accreditation_certificate"]["status"] == "manual_review"
    assert "not found" in v["accreditation_certificate"]["error"]
    ids = rule_ids(report(client, officer, app_id))
    assert {"VER-003", "VER-004"} <= ids


def test_no_reference_means_manual_review(client, auth_header, make_pdf):
    app_id, officer = _submit_with(client, auth_header, {"fire_noc": make_pdf("fire_noc", "missing_field")})
    v = _verifications(client, officer, app_id)["fire_noc"]
    assert v["status"] == "manual_review" and "No reference" in v["error"]


def test_missing_issuer_data_is_source_unavailable(client, auth_header, make_pdf, tmp_path, monkeypatch):
    gen = make_pdf("fire_noc")
    monkeypatch.setattr(settings, "mock_issuer_data_path", tmp_path / "does_not_exist.json")
    app_id, officer = _submit_with(client, auth_header, {"fire_noc": gen})
    assert _verifications(client, officer, app_id)["fire_noc"]["status"] == "source_unavailable"


def test_verification_is_audited_with_masked_reference(client, auth_header, make_pdf, db):
    gen = make_pdf("fire_noc")
    _submit_with(client, auth_header, {"fire_noc": gen})
    event = db.execute(select(AuditEvent).where(AuditEvent.event_type == "verification.completed")).scalars().first()
    assert event.payload["status"] == "verified" and event.payload["is_mock"] is True
    assert event.payload["reference"].endswith(gen.qr_ref[-4:]) and gen.qr_ref not in event.payload["reference"]


def test_staff_only_and_manual_reverify(client, auth_header, make_pdf):
    gen = _with_record_change(make_pdf, "fire_noc", status="pending")
    app_id, officer = _submit_with(client, auth_header, {"fire_noc": gen})
    applicant = auth_header(Role.applicant)
    assert client.get(f"/api/applications/{app_id}/verifications", headers=applicant).status_code == 403
    assert report(client, applicant, app_id)["verifications"] == []

    register_issuer_record(gen)  # the issuer has now processed it
    doc_id = _verifications(client, officer, app_id)["fire_noc"]["document_id"]
    assert client.post(f"/api/documents/{doc_id}/verify", headers=applicant).status_code == 403
    res = client.post(f"/api/documents/{doc_id}/verify", headers=officer)
    assert res.status_code == 200 and res.json()["status"] == "verified"
    assert "VER-004" not in rule_ids(report(client, officer, app_id))  # validation re-ran
