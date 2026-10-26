"""Application workflow and permission tests through the API."""
import pytest
from sqlalchemy import select

from app.enums import Role
from app.models import ApplicationVersion, AuditEvent, Notification
from tests.helpers import create_app, report, rule_ids, submitted_under_scrutiny, upload, upload_set


def test_only_applicants_create(client, auth_header):
    for role in (Role.scrutiny_officer, Role.admin):
        res = client.post("/api/applications", headers=auth_header(role),
                          json={"category": "eoa_no_change", "academic_year": "2027-28"})
        assert res.status_code == 403


def test_form_field_validation(client, auth_header):
    h = auth_header(Role.applicant)
    res = client.post("/api/applications", headers=h, json={
        "category": "eoa_increase_intake", "academic_year": "2027-28", "form_data": {"requested_intake": "lots"}})
    assert res.status_code == 409
    app = create_app(client, h, "eoa_increase_intake")
    res = client.post(f"/api/applications/{app['id']}/submit", headers=h)
    assert res.status_code == 409 and "Requested total intake" in res.json()["detail"]


def test_upload_rejects_non_pdf_bytes_with_pdf_name(client, auth_header):
    h = auth_header(Role.applicant)
    app = create_app(client, h)
    res = upload(client, h, app["id"], "fire_noc", b"MZ\x90\x00 definitely not a pdf", "fake.pdf")
    assert res.status_code == 422


def test_upload_stores_sha256_and_supersedes(client, auth_header, make_pdf):
    h = auth_header(Role.applicant)
    app = create_app(client, h)
    first = upload(client, h, app["id"], "fire_noc", make_pdf("fire_noc", seed=1).pdf).json()
    second = upload(client, h, app["id"], "fire_noc", make_pdf("fire_noc", seed=2).pdf).json()
    assert len(first["sha256"]) == 64 and first["sha256"] != second["sha256"]
    current = client.get(f"/api/applications/{app['id']}/documents", headers=h).json()
    assert [d["id"] for d in current] == [second["id"]]
    history = client.get(f"/api/applications/{app['id']}/documents?include_history=true", headers=h).json()
    assert len(history) == 2


def test_other_institution_cannot_see_or_upload(client, auth_header, make_pdf):
    app = create_app(client, auth_header(Role.applicant))
    other = auth_header("other_applicant@test.local")
    assert client.get(f"/api/applications/{app['id']}", headers=other).status_code == 403
    assert client.get(f"/api/applications/{app['id']}/report", headers=other).status_code == 403
    assert upload(client, other, app["id"], "fire_noc", make_pdf("fire_noc").pdf).status_code == 403
    assert client.get("/api/applications", headers=other).json() == []


def test_staff_cannot_see_unsubmitted_drafts(client, auth_header):
    app = create_app(client, auth_header(Role.applicant))
    officer = auth_header(Role.scrutiny_officer)
    assert client.get(f"/api/applications/{app['id']}", headers=officer).status_code == 403
    assert client.get("/api/applications", headers=officer).json() == []


def test_precheck_shows_incomplete_and_findings(client, auth_header, make_pdf, monkeypatch):
    monkeypatch.setattr("app.services.extraction.ocr_available", lambda: False)
    h = auth_header(Role.applicant)
    app = create_app(client, h)
    upload(client, h, app["id"], "fire_noc", make_pdf("fire_noc", "scanned").pdf)
    upload(client, h, app["id"], "affidavit", make_pdf("affidavit").pdf)
    run = client.post(f"/api/applications/{app['id']}/validate?precheck=true", headers=h)
    assert run.status_code == 200 and run.json()["is_precheck"] is True
    rep = report(client, h, app["id"])
    assert "COMP-001" in rule_ids(rep)  # land document + faculty list missing
    assert any("Tesseract" in c["reason"] for c in rep["incomplete_checks"])
    assert rep["run"]["rule_set_version"].startswith("core@v")


def test_officer_cannot_precheck_and_applicant_cannot_run_official(client, auth_header, make_pdf):
    app_id, applicant, officer = submitted_under_scrutiny(client, auth_header, make_pdf)
    assert client.post(f"/api/applications/{app_id}/validate?precheck=true", headers=officer).status_code == 403
    assert client.post(f"/api/applications/{app_id}/validate", headers=applicant).status_code == 403
    assert client.post(f"/api/applications/{app_id}/validate", headers=officer).status_code == 200


def test_applicant_cannot_make_decisions(client, auth_header, make_pdf):
    app_id, applicant, _ = submitted_under_scrutiny(client, auth_header, make_pdf)
    res = client.post(f"/api/applications/{app_id}/decision", headers=applicant,
                      json={"decision": "mark_scrutiny_complete", "reason": "looks fine to me"})
    assert res.status_code == 403
    assert client.post(f"/api/applications/{app_id}/start-scrutiny", headers=applicant).status_code == 403


def test_decision_needs_reason_and_blocks_on_open_critical(client, auth_header, make_pdf):
    app_id, _, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "expired"})
    res = client.post(f"/api/applications/{app_id}/decision", headers=officer,
                      json={"decision": "mark_scrutiny_complete", "reason": "no"})
    assert res.status_code == 422  # reason too short (schema)
    res = client.post(f"/api/applications/{app_id}/decision", headers=officer,
                      json={"decision": "mark_scrutiny_complete", "reason": "all checks reviewed"})
    assert res.status_code == 409 and "critical/high" in res.json()["detail"]


def test_return_resubmit_creates_new_version(client, auth_header, make_pdf, db):
    app_id, applicant, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "expired"})
    res = client.post(f"/api/applications/{app_id}/decision", headers=officer,
                      json={"decision": "return_for_correction", "reason": "Fire NOC has expired"})
    assert res.json()["status"] == "returned_for_correction" and res.json()["current_version"] == 2
    assert "awaiting_correction" in {n.kind for n in db.execute(select(Notification)).scalars()}

    assert upload(client, applicant, app_id, "fire_noc", make_pdf("fire_noc", seed=9).pdf).status_code == 201
    assert client.post(f"/api/applications/{app_id}/submit", headers=applicant).json()["status"] == "submitted"
    versions = client.get(f"/api/applications/{app_id}/versions", headers=applicant).json()
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[0]["snapshot"]["documents"] != versions[1]["snapshot"]["documents"]
    assert db.query(ApplicationVersion).count() == 2

    client.post(f"/api/applications/{app_id}/start-scrutiny", headers=officer)
    assert "EXP-001" not in rule_ids(report(client, officer, app_id))
    events = {e.event_type for e in db.execute(select(AuditEvent)).scalars()}
    assert {"application.resubmitted", "application.return_for_correction", "document.superseded"} <= events


def test_escalation_goes_to_senior(client, auth_header, make_pdf):
    app_id, _, officer = submitted_under_scrutiny(client, auth_header, make_pdf)
    res = client.post(f"/api/applications/{app_id}/decision", headers=officer,
                      json={"decision": "escalate", "reason": "needs senior view"})
    assert res.json()["status"] == "escalated"
    again = client.post(f"/api/applications/{app_id}/decision", headers=officer,
                        json={"decision": "mark_scrutiny_complete", "reason": "trying anyway"})
    assert again.status_code == 409
    senior = auth_header(Role.senior_authority)
    done = client.post(f"/api/applications/{app_id}/decision", headers=senior,
                       json={"decision": "mark_scrutiny_complete", "reason": "reviewed escalated case"})
    assert done.status_code == 200 and done.json()["status"] == "scrutiny_complete"
    # Inspector sees escalated cases only; this one is now complete.
    assert client.get(f"/api/applications/{app_id}", headers=auth_header(Role.inspector)).status_code == 403


@pytest.mark.parametrize("action, status", [("resolve", "resolved"), ("dismiss", "dismissed"), ("escalate", "escalated")])
def test_finding_review_actions(client, auth_header, make_pdf, action, status):
    app_id, applicant, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "expired"})
    finding = next(f for f in report(client, officer, app_id)["findings"] if f["rule_id"] == "EXP-001")
    assert client.post(f"/api/findings/{finding['id']}/review", headers=applicant,
                       json={"action": action, "reason": "applicant tries"}).status_code == 403
    res = client.post(f"/api/findings/{finding['id']}/review", headers=officer,
                      json={"action": action, "reason": "checked the renewal"})
    assert res.status_code == 200 and res.json()["status"] == status
    again = client.post(f"/api/findings/{finding['id']}/review", headers=officer,
                        json={"action": "resolve", "reason": "second time"})
    assert again.status_code == 409


def test_review_carries_over_to_rerun(client, auth_header, make_pdf):
    app_id, _, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "expired"})
    finding = next(f for f in report(client, officer, app_id)["findings"] if f["rule_id"] == "EXP-001")
    client.post(f"/api/findings/{finding['id']}/review", headers=officer,
                json={"action": "dismiss", "reason": "renewal receipt seen"})
    client.post(f"/api/applications/{app_id}/validate", headers=officer)
    rerun = next(f for f in report(client, officer, app_id)["findings"] if f["rule_id"] == "EXP-001")
    assert rerun["id"] != finding["id"] and rerun["status"] == "dismissed"
    assert "carried over" in rerun["review_reason"]


def test_officer_field_correction_is_audited_and_masked(client, auth_header, make_pdf, db):
    app_id, applicant, officer = submitted_under_scrutiny(client, auth_header, make_pdf)
    rep = report(client, officer, app_id)
    noc = next(d for d in rep["documents"] if d["doc_type"] == "fire_noc")
    field = next(f for f in noc["fields"] if f["field_name"] == "certificate_number")
    body = {"value": "FNOC-2026-999999", "reason": "typo corrected from original"}
    assert client.patch(f"/api/fields/{field['id']}", headers=applicant, json=body).status_code == 403
    res = client.patch(f"/api/fields/{field['id']}", headers=officer, json=body)
    assert res.status_code == 200 and res.json()["source"] == "manual"
    assert res.json()["bbox"] == field["bbox"]
    event = db.execute(select(AuditEvent).where(AuditEvent.event_type == "field.corrected")).scalar_one()
    assert event.payload["new_value"].endswith("9999") and event.payload["new_value"].startswith("*")


def test_file_link_is_short_lived_and_permissioned(client, auth_header, make_pdf):
    h = auth_header(Role.applicant)
    app = create_app(client, h)
    gen = make_pdf("affidavit")
    doc = upload(client, h, app["id"], "affidavit", gen.pdf).json()
    other = auth_header("other_applicant@test.local")
    assert client.post(f"/api/documents/{doc['id']}/link", headers=other).status_code == 403
    link = client.post(f"/api/documents/{doc['id']}/link", headers=h).json()
    assert link["expires_in_seconds"] == 300
    file_res = client.get(link["url"])
    assert file_res.status_code == 200 and file_res.content == gen.pdf
    assert client.get("/api/files/not-a-token").status_code == 403


def test_name_mismatch_and_ter_pending(client, auth_header, make_pdf, db):
    from app.models import Institution

    inst = db.execute(select(Institution).where(Institution.aicte_ref == "SYN-TEST-0001")).scalar_one()
    inst.ter_payment_status = "pending"
    db.commit()
    app_id, _, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"land_document": "name_mismatch"})
    ids = rule_ids(report(client, officer, app_id))
    assert {"CONS-001", "REC-001"} <= ids


def test_conditional_document_required_for_large_increase(client, auth_header, make_pdf):
    h = auth_header(Role.applicant)
    app = create_app(client, h, "eoa_increase_intake", {"requested_intake": 240})
    upload_set(client, h, app["id"], make_pdf)
    checklist = client.get(f"/api/applications/{app['id']}/checklist", headers=h).json()
    acc = next(c for c in checklist if c["doc_type"] == "accreditation_certificate")
    assert acc["requirement"] == "required" and not acc["uploaded"]
    client.post(f"/api/applications/{app['id']}/validate?precheck=true", headers=h)
    missing = [f for f in report(client, h, app["id"])["findings"] if f["rule_id"] == "COMP-001"]
    assert len(missing) == 1 and "Accreditation" in missing[0]["title"]


def test_dashboard_counts_only_latest_official_run(client, auth_header, make_pdf):
    h = auth_header(Role.applicant)
    app = create_app(client, h)
    upload_set(client, h, app["id"], make_pdf, {"fire_noc": "expired"})
    client.post(f"/api/applications/{app['id']}/validate?precheck=true", headers=h)  # not counted
    client.post(f"/api/applications/{app['id']}/submit", headers=h)
    officer = auth_header(Role.scrutiny_officer)
    client.post(f"/api/applications/{app['id']}/validate", headers=officer)  # re-run replaces the first run
    # EXP-001 (printed date) + VER-002 (MOCK issuer confirms expiry), from the latest run only
    assert client.get("/api/dashboard", headers=officer).json()["counts"]["open_findings"] == 2
