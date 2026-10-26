"""visible_to_applicant is enforced in the backend: applicants never receive hidden findings."""
from app.enums import FindingCategory, Role, Severity
from app.models import Finding, ValidationRun
from tests.helpers import report, submitted_under_scrutiny


def _add_hidden_findings(db, app_id: str, run_id: str) -> None:
    common = dict(application_id=app_id, validation_run_id=run_id, rule_version="1", explanation="test",
                  suggested_action="review manually", evidence=None)
    db.add(Finding(rule_id="ANO-001", category=FindingCategory.anomaly, severity=Severity.medium,
                   title="Preliminary indicator: metadata irregularity", visible_to_applicant=False, **common))
    db.add(Finding(rule_id="INT-001", category=FindingCategory.consistency, severity=Severity.low,
                   title="Internal only", visible_to_applicant=False, **common))
    db.commit()


def test_applicant_report_excludes_hidden_findings(client, auth_header, make_pdf, db):
    app_id, applicant, officer = submitted_under_scrutiny(client, auth_header, make_pdf, {"fire_noc": "expired"})
    run = db.query(ValidationRun).filter_by(application_id=app_id, is_precheck=False).one()
    _add_hidden_findings(db, app_id, run.id)

    staff_ids = {f["rule_id"] for f in report(client, officer, app_id)["findings"]}
    applicant_report = report(client, applicant, app_id)
    applicant_ids = {f["rule_id"] for f in applicant_report["findings"]}

    assert {"ANO-001", "INT-001", "EXP-001"} <= staff_ids
    assert "EXP-001" in applicant_ids
    assert not {"ANO-001", "INT-001"} & applicant_ids
    assert all(f["visible_to_applicant"] for f in applicant_report["findings"])
    assert sum(applicant_report["summary"].values()) == len(applicant_report["findings"])


def test_low_confidence_rule_is_staff_only(client, auth_header, make_pdf, db):
    app_id, applicant, officer = submitted_under_scrutiny(client, auth_header, make_pdf)
    run = db.query(ValidationRun).filter_by(application_id=app_id).one()
    db.add(Finding(application_id=app_id, validation_run_id=run.id, rule_id="EXT-001", rule_version="1",
                   category=FindingCategory.completeness, severity=Severity.info, title="confirm value",
                   explanation="x", suggested_action="confirm", visible_to_applicant=False))
    db.commit()
    assert "EXT-001" in {f["rule_id"] for f in report(client, officer, app_id)["findings"]}
    assert "EXT-001" not in {f["rule_id"] for f in report(client, applicant, app_id)["findings"]}


def test_staff_do_not_get_applicant_prechecks(client, auth_header, make_pdf):
    from tests.helpers import create_app

    h = auth_header(Role.applicant)
    app = create_app(client, h)
    client.post(f"/api/applications/{app['id']}/validate?precheck=true", headers=h)
    client.post(f"/api/applications/{app['id']}/submit", headers=h)
    officer = auth_header(Role.scrutiny_officer)
    runs = client.get(f"/api/applications/{app['id']}/runs", headers=officer).json()
    assert len(runs) == 1 and runs[0]["is_precheck"] is False
    assert report(client, officer, app["id"])["run"]["is_precheck"] is False
