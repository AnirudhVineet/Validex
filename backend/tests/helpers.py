"""Small API helpers shared by workflow tests."""
from app.enums import Role

ALL_REQUIRED = ["fire_noc", "affidavit", "land_document", "faculty_list"]


def create_app(client, headers, category="eoa_no_change", form_data=None) -> dict:
    res = client.post("/api/applications", headers=headers,
                      json={"category": category, "academic_year": "2027-28", "form_data": form_data or {}})
    assert res.status_code == 201, res.text
    return res.json()


def upload(client, headers, app_id, doc_type, pdf: bytes, filename=None):
    return client.post(f"/api/applications/{app_id}/documents", headers=headers,
                       data={"doc_type": doc_type},
                       files={"file": (filename or f"{doc_type}.pdf", pdf, "application/pdf")})


def upload_set(client, headers, app_id, make_pdf, variants: dict | None = None, skip=()):
    """Upload all required docs (valid unless a variant is given)."""
    variants = variants or {}
    for i, doc_type in enumerate(ALL_REQUIRED):
        if doc_type in skip:
            continue
        res = upload(client, headers, app_id, doc_type, make_pdf(doc_type, variants.get(doc_type, "valid"), seed=i).pdf)
        assert res.status_code == 201, res.text


def submitted_under_scrutiny(client, auth_header, make_pdf, variants=None, skip=()) -> tuple[str, dict, dict]:
    """Create, fill, submit and start scrutiny. Returns (app_id, applicant headers, officer headers)."""
    applicant, officer = auth_header(Role.applicant), auth_header(Role.scrutiny_officer)
    app = create_app(client, applicant)
    upload_set(client, applicant, app["id"], make_pdf, variants, skip)
    assert client.post(f"/api/applications/{app['id']}/submit", headers=applicant).status_code == 200
    assert client.post(f"/api/applications/{app['id']}/start-scrutiny", headers=officer).status_code == 200
    return app["id"], applicant, officer


def report(client, headers, app_id) -> dict:
    res = client.get(f"/api/applications/{app_id}/report", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def rule_ids(rep: dict) -> set[str]:
    return {f["rule_id"] for f in rep["findings"]}
