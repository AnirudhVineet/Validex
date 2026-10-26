"""Anomaly visibility, priority score, alerts, rule editor, evidence pages."""
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.enums import Role, VerificationStatus
from app.models import Finding, Notification, RuleSetVersion, ValidationRun, VerificationRequest
from app.models.base import utcnow
from app.services.rules.checks import irregular_dates, qr_reference_mismatch, NoParams
from app.services.rules.context import DocView, FieldView, InstitutionView, ValidationContext
from tests.conftest import register_issuer_record
from tests.helpers import create_app, report, rule_ids, submitted_under_scrutiny, upload, upload_set

# ---------- anomaly indicators ----------


def test_anomalies_are_staff_only_and_worded_as_preliminary(client, auth_header, make_pdf):
    app_id, applicant, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "altered"})
    staff = report(client, officer, app_id)
    anomalies = [f for f in staff["findings"] if f["category"] == "anomaly"]
    assert anomalies and all(f["title"].startswith("Preliminary indicator") for f in anomalies)
    assert all(not f["visible_to_applicant"] for f in anomalies)
    for f in staff["findings"]:
        text = f"{f['title']} {f['explanation']}".lower()
        assert "fraud" not in text and "forged" not in text
    seen_by_applicant = report(client, applicant, app_id)
    assert not [f for f in seen_by_applicant["findings"] if f["category"] in ("anomaly", "verification")]
    assert seen_by_applicant["priority"] is None


def test_exact_duplicate_in_two_slots(client, auth_header, make_pdf):
    h = auth_header(Role.applicant)
    app = create_app(client, h)
    affidavit = make_pdf("affidavit").pdf
    upload(client, h, app["id"], "affidavit", affidavit)
    upload(client, h, app["id"], "land_document", affidavit)
    client.post(f"/api/applications/{app['id']}/submit", headers=h)
    ids = rule_ids(report(client, auth_header(Role.scrutiny_officer), app["id"]))
    assert {"ANO-001", "COMP-003"} <= ids


def test_clean_application_has_no_anomaly_or_verification_findings(client, auth_header, make_pdf):
    app_id, _, officer = submitted_under_scrutiny(client, auth_header, make_pdf)
    cats = {f["category"] for f in report(client, officer, app_id)["findings"]}
    assert not cats & {"anomaly", "verification"}


def test_signed_document_reports_presence_only(client, auth_header, make_pdf):
    h = auth_header(Role.applicant)
    app = create_app(client, h)
    upload_set(client, h, app["id"], make_pdf)
    upload(client, h, app["id"], "accreditation_certificate", make_pdf("accreditation_certificate", "signed").pdf)
    client.post(f"/api/applications/{app['id']}/submit", headers=h)
    sig = [f for f in report(client, auth_header(Role.scrutiny_officer), app["id"])["findings"] if f["rule_id"] == "SIG-001"]
    assert len(sig) == 1 and "not validated" in sig[0]["title"] and sig[0]["severity"] == "info"


def _ctx(doc):
    inst = InstitutionView("x", "y", 1, 1, "none", "paid")
    return ValidationContext(institution=inst, documents={doc.doc_type: doc}, checklist=[], today=utcnow().date())


def test_qr_reference_and_irregular_date_checks():
    f = lambda n, v: FieldView(n, v, 0.98, 1, [1, 2, 3, 4], "pdf_text", False)  # noqa: E731
    doc = DocView("d", "fire_noc", "extracted", "fire_noc", None,
                  {"certificate_number": f("certificate_number", "FNOC-2026-000001"), "issue_date": f("issue_date", "2026-05-01")},
                  analysis={"qr": [{"ref": "FNOC-2026-999999"}],
                            "pdf": {"creation_date": "2026-01-01T00:00:00+00:00", "mod_date": "2025-12-01T00:00:00+00:00"}})
    assert len(qr_reference_mismatch(_ctx(doc), NoParams()).findings) == 1
    notes = irregular_dates(_ctx(doc), NoParams()).findings[0].found_value
    assert "before the printed issue date" in notes and "before creation date" in notes


# ---------- priority ----------


def test_priority_breakdown_and_visibility(client, auth_header, make_pdf):
    app_id, applicant, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "altered"})
    res = client.get(f"/api/applications/{app_id}/priority", headers=officer).json()
    assert res["score"] == min(100, sum(f["points"] for f in res["factors"]))
    assert {"preliminary anomaly indicators", "issuer verification issues"} <= {f["factor"] for f in res["factors"]}
    assert "Not a probability" in res["description"]
    assert client.get(f"/api/applications/{app_id}/priority", headers=applicant).status_code == 403
    assert client.get("/api/applications", headers=applicant).json()[0]["priority_score"] is None
    queue = client.get("/api/applications", headers=officer).json()
    assert queue[0]["priority_score"] == res["score"]


def test_clean_case_scores_lower_than_problem_case(client, auth_header, make_pdf):
    clean_id, _, officer = submitted_under_scrutiny(client, auth_header, make_pdf)
    bad_id, _, _ = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "expired"})
    score = lambda i: client.get(f"/api/applications/{i}/priority", headers=officer).json()["score"]  # noqa: E731
    assert score(bad_id) > score(clean_id)


# ---------- alerts ----------


def test_alerts_for_applicant_and_officer(client, auth_header, make_pdf, db):
    app_id, applicant, officer = submitted_under_scrutiny(client, auth_header, make_pdf,
                                                          {"fire_noc": "altered"}, skip=("affidavit",))
    applicant_kinds = {n["kind"] for n in client.get("/api/notifications", headers=applicant).json()}
    officer_kinds = {n["kind"] for n in client.get("/api/notifications", headers=officer).json()}
    assert "missing" in applicant_kinds and "anomaly" not in applicant_kinds
    assert "anomaly" in officer_kinds
    # Re-running validation does not duplicate unread alerts.
    before = db.query(Notification).count()
    client.post(f"/api/applications/{app_id}/validate", headers=officer)
    assert db.query(Notification).count() == before


def test_pending_verification_alert_after_threshold(client, auth_header, make_pdf, db):
    gen = make_pdf("fire_noc")
    register_issuer_record(gen, status="pending")
    h = auth_header(Role.applicant)
    app = create_app(client, h)
    upload(client, h, app["id"], "fire_noc", gen.pdf)
    client.post(f"/api/applications/{app['id']}/submit", headers=h)
    officer = auth_header(Role.scrutiny_officer)
    assert "pending_verification" not in {n["kind"] for n in client.get("/api/notifications", headers=officer).json()}
    req = db.execute(select(VerificationRequest).where(VerificationRequest.status == VerificationStatus.pending)).scalar_one()
    req.requested_at = utcnow() - timedelta(hours=30)
    db.commit()
    notes = client.get("/api/notifications", headers=officer).json()
    pending = [n for n in notes if n["kind"] == "pending_verification"]
    assert len(pending) == 1
    other = auth_header(Role.senior_authority)
    assert client.post(f"/api/notifications/{pending[0]['id']}/read", headers=other).status_code == 404
    assert client.post(f"/api/notifications/{pending[0]['id']}/read", headers=officer).json()["read_at"]


# ---------- rule editor ----------


@pytest.mark.parametrize("call", [
    ("post", "/api/rules/validate", {"content_yaml": "x"}),
    ("put", "/api/rules", {"content_yaml": "x", "reason": "trying it"}),
    ("post", "/api/rules/rerun", None),
])
def test_officer_and_applicant_cannot_edit_rules(client, auth_header, call):
    method, url, body = call
    for role in (Role.scrutiny_officer, Role.applicant, Role.inspector):
        res = getattr(client, method)(url, headers=auth_header(role), **({"json": body} if body else {}))
        assert res.status_code == 403, (role, url)


def test_validate_reports_errors(client, auth_header):
    res = client.post("/api/rules/validate", headers=auth_header(Role.admin),
                      json={"content_yaml": "illustrative: true\nname: core\nversion: 1\nrules: []"})
    assert res.json()["valid"] is False and res.json()["errors"]


def test_save_bumps_version_and_rerun_keeps_old_results(client, auth_header, make_pdf, db):
    app_id, _, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "near_expiry"})
    assert "EXP-002" in rule_ids(report(client, officer, app_id))
    old_run_id = report(client, officer, app_id)["run"]["id"]

    senior = auth_header(Role.senior_authority)
    current = client.get("/api/rules", headers=senior).json()
    edited = current["content_yaml"].replace("params: {within_days: 90}", "params: {within_days: 10}")
    assert client.put("/api/rules", headers=senior, json={"content_yaml": current["content_yaml"], "reason": "no change"}).status_code == 409
    bad = client.put("/api/rules", headers=senior, json={"content_yaml": edited.replace("severity: low", "severity: urgent"), "reason": "typo test"})
    assert bad.status_code == 422
    saved = client.put("/api/rules", headers=senior, json={"content_yaml": edited, "reason": "shorter renewal window"})
    assert saved.status_code == 200 and saved.json()["version"] == current["version"] + 1
    assert f"version: {current['version'] + 1}" in saved.json()["content_yaml"]

    rerun = client.post("/api/rules/rerun", headers=auth_header(Role.admin)).json()
    assert rerun["applications_rerun"] >= 1 and rerun["rule_set_version"].endswith(str(current["version"] + 1))
    new = report(client, officer, app_id)
    assert new["run"]["id"] != old_run_id and "EXP-002" not in rule_ids(new)
    old_findings = db.execute(select(Finding).where(Finding.validation_run_id == old_run_id)).scalars().all()
    assert any(f.rule_id == "EXP-002" for f in old_findings)  # old results preserved
    assert db.get(ValidationRun, old_run_id).rule_set_version.endswith(f"v{current['version']}")
    versions = client.get("/api/rules/versions", headers=officer).json()
    assert [v["is_active"] for v in versions] == [True, False]
    assert db.query(RuleSetVersion).count() >= 2


# ---------- evidence pages ----------


def test_page_png_for_evidence_highlighting(client, auth_header, make_pdf):
    h = auth_header(Role.applicant)
    app = create_app(client, h)
    doc = upload(client, h, app["id"], "fire_noc", make_pdf("fire_noc").pdf).json()
    link = client.post(f"/api/documents/{doc['id']}/link", headers=h).json()
    assert link["pages"] == 1 and link["page_scale"] == 2.0
    page = client.get(link["page_url_template"].replace("{page}", "1"))
    assert page.status_code == 200 and page.content.startswith(b"\x89PNG")
    assert client.get(link["page_url_template"].replace("{page}", "5")).status_code == 404
    assert client.get("/api/files/bad-token/pages/1").status_code == 403
