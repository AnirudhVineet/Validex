import pytest

from app.enums import Role


def test_login_success_returns_token_and_user(client):
    res = client.post("/api/auth/login", json={"email": "admin@test.local", "password": "test-pass"})
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "admin"
    assert "password_hash" not in body["user"]


def test_login_wrong_password_is_401(client):
    res = client.post("/api/auth/login", json={"email": "admin@test.local", "password": "nope"})
    assert res.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_rejects_garbage_token(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert res.status_code == 401


def test_me_returns_current_user(client, auth_header):
    res = client.get("/api/auth/me", headers=auth_header(Role.scrutiny_officer))
    assert res.status_code == 200
    assert res.json()["role"] == "scrutiny_officer"


@pytest.mark.parametrize("role", [r for r in Role if r != Role.admin])
def test_user_list_forbidden_for_non_admin(client, auth_header, role):
    assert client.get("/api/users", headers=auth_header(role)).status_code == 403


def test_user_list_allowed_for_admin(client, auth_header):
    res = client.get("/api/users", headers=auth_header(Role.admin))
    assert res.status_code == 200
    assert len(res.json()) == len(Role) + 1  # + the other institution's applicant


@pytest.mark.parametrize("role", [Role.applicant, Role.inspector])
def test_audit_forbidden_for_applicant_and_inspector(client, auth_header, role):
    headers = auth_header(role)
    assert client.get("/api/audit", headers=headers).status_code == 403
    assert client.get("/api/audit/verify", headers=headers).status_code == 403


@pytest.mark.parametrize("role", list(Role))
def test_every_role_gets_a_dashboard(client, auth_header, role):
    res = client.get("/api/dashboard", headers=auth_header(role))
    assert res.status_code == 200
    assert res.json()["role"] == role.value
