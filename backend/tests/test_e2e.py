"""Acceptance test: seed -> login -> upload -> validate -> report -> officer review -> audit verify."""
import random
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.models import AuditEvent

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from seed import seed as seed_script  # noqa: E402
from seed.docgen import InstitutionData, make_document  # noqa: E402


def test_demo_path_end_to_end(client, db, monkeypatch):
    # 1. Seed (users only + demo institution) into the test database.
    monkeypatch.setattr(seed_script, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    seed_script.seed_users_and_demo_institution()
    demo = seed_script.DEMO_INSTITUTION
    inst = InstitutionData(demo["name"], demo["address"], demo["aicte_ref"], demo["state"], demo["faculty_count"])

    def login(email):
        res = client.post("/api/auth/login", json={"email": email, "password": seed_script.DEMO_PASSWORD})
        assert res.status_code == 200, res.text
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    # 2. Applicant logs in, creates an application, uploads documents (one expired).
    applicant = login("applicant@validex.demo")
    app = client.post("/api/applications", headers=applicant,
                      json={"category": "eoa_no_change", "academic_year": "2027-28"}).json()
    rng = random.Random(7)
    for doc_type, variant in [("fire_noc", "expired"), ("affidavit", "valid"),
                              ("land_document", "valid"), ("faculty_list", "valid")]:
        pdf = make_document(doc_type, variant, inst, date.today(), rng).pdf
        res = client.post(f"/api/applications/{app['id']}/documents", headers=applicant,
                          data={"doc_type": doc_type}, files={"file": (f"{doc_type}.pdf", pdf, "application/pdf")})
        assert res.status_code == 201 and res.json()["status"] == "extracted", res.text

    # 3. Pre-check, then submit (official validation runs on submit).
    pre = client.post(f"/api/applications/{app['id']}/validate?precheck=true", headers=applicant).json()
    assert pre["is_precheck"]
    pre_report = client.get(f"/api/applications/{app['id']}/report", headers=applicant).json()
    assert [f["rule_id"] for f in pre_report["findings"]] == ["EXP-001"]
    assert client.post(f"/api/applications/{app['id']}/submit", headers=applicant).status_code == 200

    # 4. Officer picks it up and reads the report with evidence.
    officer = login("officer@validex.demo")
    queue = client.get("/api/applications?status=submitted", headers=officer).json()
    assert [a["id"] for a in queue] == [app["id"]] and queue[0]["critical_findings"] == 1
    client.post(f"/api/applications/{app['id']}/start-scrutiny", headers=officer)
    rep = client.get(f"/api/applications/{app['id']}/report", headers=officer).json()
    expired = next(f for f in rep["findings"] if f["rule_id"] == "EXP-001")
    for key in ("found_value", "expected_value", "explanation", "suggested_action", "rule_version"):
        assert expired[key]
    assert expired["evidence"]["page"] == 1 and len(expired["evidence"]["bbox"]) == 4

    # 5. Officer reviews: cannot complete while critical is open; resolves, then completes.
    blocked = client.post(f"/api/applications/{app['id']}/decision", headers=officer,
                          json={"decision": "mark_scrutiny_complete", "reason": "all reviewed"})
    assert blocked.status_code == 409
    client.post(f"/api/findings/{expired['id']}/review", headers=officer,
                json={"action": "resolve", "reason": "renewed NOC verified offline (demo)"})
    done = client.post(f"/api/applications/{app['id']}/decision", headers=officer,
                       json={"decision": "mark_scrutiny_complete", "reason": "all findings reviewed"})
    assert done.status_code == 200 and done.json()["status"] == "scrutiny_complete"

    # 6. Audit trail is complete and the hash chain verifies.
    admin = login("admin@validex.demo")
    verify = client.get("/api/audit/verify", headers=admin).json()
    assert verify["valid"] is True
    types = [e.event_type for e in db.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars()]
    for expected in ["user.seeded", "user.login", "application.created", "document.uploaded",
                     "document.extracted", "validation.run", "application.submitted",
                     "application.scrutiny_started", "finding.resolved", "application.mark_scrutiny_complete"]:
        assert expected in types, expected
