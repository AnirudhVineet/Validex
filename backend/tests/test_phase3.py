"""Cross-application intelligence, dashboards, inspector flow, deficiency letter, LLM summary."""
import pytest
from sqlalchemy import select

from app.config import settings
from app.enums import Role
from app.models import ApplicationDocument, AuditEvent, Finding
from app.services import summary
from seed import docgen
from tests.helpers import create_app, report, rule_ids, submitted_under_scrutiny, upload, upload_set

OTHER = "other_applicant@test.local"


def _escalated_case(client, auth_header, make_pdf, variants=None):
    app_id, applicant, officer = submitted_under_scrutiny(client, auth_header, make_pdf, variants)
    client.post(f"/api/applications/{app_id}/decision", headers=officer,
                json={"decision": "escalate", "reason": "needs a site inspection"})
    return app_id, applicant, officer


# ---------- cross-application ----------

def test_cross_application_matches_are_officer_only(client, auth_header, make_pdf):
    applicant, officer = auth_header(Role.applicant), auth_header(Role.scrutiny_officer)
    first = create_app(client, applicant)
    first_id = first["id"]
    upload_set(client, applicant, first_id, make_pdf, skip=("land_document",))
    land = make_pdf("land_document", seed=2).pdf
    upload(client, applicant, first_id, "land_document", land)
    client.post(f"/api/applications/{first_id}/submit", headers=applicant)
    first_faculty = make_pdf("faculty_list", seed=3).truth["faculty_ids"].split(",")

    other = auth_header(OTHER)
    app = create_app(client, other)
    upload(client, other, app["id"], "land_document", land)
    shared = make_pdf("faculty_list", seed=11, shared_faculty_ids=first_faculty[:4])
    upload(client, other, app["id"], "faculty_list", shared.pdf)
    client.post(f"/api/applications/{app['id']}/submit", headers=other)

    staff = report(client, officer, app["id"])
    assert {"XAPP-001", "XAPP-002", "XAPP-003"} <= rule_ids(staff)
    xapp = [f for f in staff["findings"] if f["rule_id"].startswith("XAPP")]
    assert all(not f["visible_to_applicant"] and "legitimate explanation" in f["explanation"] for f in xapp)
    assert not {f["rule_id"] for f in report(client, other, app["id"])["findings"]} & {"XAPP-001", "XAPP-002", "XAPP-003"}
    # The first institution's own re-run now also sees the match (other institution, submitted).
    client.post(f"/api/applications/{first_id}/validate", headers=officer)
    assert "XAPP-001" in rule_ids(report(client, officer, first_id))


def test_same_institution_reuse_is_not_flagged(client, auth_header, make_pdf):
    submitted_under_scrutiny(client, auth_header, make_pdf)
    second_id, _, officer = submitted_under_scrutiny(client, auth_header, make_pdf)  # same files, same institution
    assert not any(r.startswith("XAPP") for r in rule_ids(report(client, officer, second_id)))


# ---------- dashboards ----------

def test_expiry_forecast_window_and_permissions(client, auth_header, make_pdf):
    submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "near_expiry"})
    officer = auth_header(Role.scrutiny_officer)
    wide = client.get("/api/dashboard/expiry-forecast?days=90", headers=officer).json()
    assert [i["doc_type"] for i in wide["items"]] == ["fire_noc"] and 0 <= wide["items"][0]["days_left"] <= 90
    assert client.get("/api/dashboard/expiry-forecast?days=5", headers=officer).json()["items"] == []
    assert client.get("/api/dashboard/expiry-forecast", headers=auth_header(Role.applicant)).status_code == 403


def test_senior_overview(client, auth_header, make_pdf):
    submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "expired"})
    assert client.get("/api/dashboard/senior", headers=auth_header(Role.scrutiny_officer)).status_code == 403
    data = client.get("/api/dashboard/senior", headers=auth_header(Role.senior_authority)).json()
    assert data["status_counts"]["under_scrutiny"] == 1 and data["open_applications"] == 1
    assert sum(data["ageing"].values()) == 1
    assert {"EXP-001", "VER-002"} <= {d["rule_id"] for d in data["common_deficiencies"]}


def test_time_saved_states_its_assumption(client, auth_header, make_pdf):
    submitted_under_scrutiny(client, auth_header, make_pdf)
    data = client.get("/api/dashboard/time-saved", headers=auth_header(Role.scrutiny_officer)).json()
    i = data["inputs"]
    assert i["documents_auto_checked"] == 4 and i["issuer_verifications"] == 2 and i["official_validation_runs"] == 1
    assert data["minutes"] == 4 * 6 + 2 * 4 + 1 * 10
    assert "ASSUMPTION" in data["assumption"]


# ---------- inspector ----------

def test_inspector_flow_and_advisory(client, auth_header, make_pdf, db):
    app_id, applicant, officer = submitted_under_scrutiny(client, auth_header, make_pdf)
    inspector = auth_header(Role.inspector)
    body = {"notes": "Visited campus", "evidence_label": "laboratory"}
    photo = docgen.to_jpeg(make_pdf("affidavit").pdf)
    files = {"file": ("lab.jpg", photo, "image/jpeg")}
    url = f"/api/applications/{app_id}/inspections"
    assert client.post(url, headers=inspector, data=body, files=files).status_code == 403  # not flagged yet

    client.post(f"/api/applications/{app_id}/decision", headers=officer,
                json={"decision": "escalate", "reason": "needs a site inspection"})
    assert client.get("/api/applications", headers=inspector).json()[0]["id"] == app_id
    assert client.post(url, headers=inspector, data={**body, "evidence_label": "swimming_pool"}, files=files).status_code == 422
    res = client.post(url, headers=inspector, data=body, files=files)
    assert res.status_code == 201 and res.json()["evidence_label"] == "laboratory"
    assert client.post(url, headers=inspector, data={"notes": "Library closed during visit"}).status_code == 201
    assert client.post(url, headers=officer, data=body).status_code == 403

    advisory = client.get(f"/api/applications/{app_id}/infrastructure", headers=auth_header(Role.senior_authority)).json()
    items = {i["key"]: i for i in advisory["items"]}
    assert items["laboratory"]["present"] and items["laboratory"]["evidence_files"] == 1
    assert not items["library"]["present"]
    assert "No area measurement" in advisory["notice"]
    assert client.get(f"/api/applications/{app_id}/inspections", headers=applicant).status_code == 403

    # Inspection evidence never enters the checklist or validation.
    rep = report(client, auth_header(Role.senior_authority), app_id)
    assert all(d["doc_type"] != "inspection_evidence" for d in rep["documents"])
    assert db.execute(select(ApplicationDocument).where(ApplicationDocument.doc_type == "inspection_evidence")).scalar_one()
    assert db.execute(select(AuditEvent).where(AuditEvent.event_type == "inspection.recorded")).scalars().first()


# ---------- deficiency letter ----------

def test_letter_uses_only_applicant_visible_findings(client, auth_header, make_pdf):
    app_id, applicant, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "altered"})
    assert client.post(f"/api/applications/{app_id}/deficiency-letter", headers=applicant).status_code == 403
    letter = client.post(f"/api/applications/{app_id}/deficiency-letter", headers=officer).json()
    assert letter["text"].startswith("DRAFT") and letter["draft"]
    staff = report(client, officer, app_id)["findings"]
    hidden = {f["id"] for f in staff if not f["visible_to_applicant"]}
    assert hidden and not hidden & set(letter["finding_ids"])
    assert "Preliminary indicator" not in letter["text"] and "issuer" not in letter["text"].lower()
    assert "approval or rejection" in letter["text"]


# ---------- optional LLM summary ----------

def test_summary_disabled_by_default(client, auth_header, make_pdf):
    app_id, applicant, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "expired"})
    res = client.post(f"/api/applications/{app_id}/summary", headers=officer).json()
    assert res["enabled"] is False and res["points"] == []
    assert client.post(f"/api/applications/{app_id}/summary", headers=applicant).status_code == 403


def test_summary_grounding_drops_uncited_points(client, auth_header, make_pdf, db, monkeypatch):
    app_id, _, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "expired"})
    findings = db.execute(select(Finding).where(Finding.application_id == app_id)).scalars().all()
    real = findings[0].id
    before = len(findings)
    monkeypatch.setattr(settings, "llm_summary_enabled", True)
    fake = {"insufficient_evidence": False, "points": [
        {"text": "The fire NOC expired.", "finding_ids": [real]},
        {"text": "Invented claim.", "finding_ids": ["not-a-finding"]},
        {"text": "No citation.", "finding_ids": []}]}
    monkeypatch.setattr(summary, "_call_model", lambda payload: fake)
    res = client.post(f"/api/applications/{app_id}/summary", headers=officer).json()
    assert res["enabled"] and res["points"] == [{"text": "The fire NOC expired.", "finding_ids": [real]}]
    assert res["dropped_points"] == 2
    assert len(db.execute(select(Finding).where(Finding.application_id == app_id)).scalars().all()) == before


@pytest.mark.parametrize("raw, insufficient", [
    (None, True),  # refusal
    ({"insufficient_evidence": True, "points": []}, True),
    ({"insufficient_evidence": False, "points": [{"text": "x", "finding_ids": ["nope"]}]}, True),
])
def test_summary_insufficient_evidence(raw, insufficient):
    assert summary.ground(raw, {"a"})["insufficient_evidence"] is insufficient


def test_summary_failure_is_contained(client, auth_header, make_pdf, monkeypatch):
    app_id, _, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "expired"})
    monkeypatch.setattr(settings, "llm_summary_enabled", True)

    def boom(_):
        raise RuntimeError("network down")

    monkeypatch.setattr(summary, "_call_model", boom)
    res = client.post(f"/api/applications/{app_id}/summary", headers=officer).json()
    assert res["insufficient_evidence"] and "unavailable" in res["note"]
