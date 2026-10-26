"""Shared fixtures: a fresh in-memory SQLite DB per test, one user per role."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base, get_db
from app.enums import Role
from app.main import app
from app.models import Institution, User
from app.services.auth import hash_password

PASSWORD = "test-pass"


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def users(db) -> dict[Role, User]:
    inst = Institution(name="SYNTHETIC Test Institute", aicte_ref="SYN-TEST-0001")
    db.add(inst)
    db.flush()
    created = {}
    for role in Role:
        user = User(
            email=f"{role.value}@test.local",
            name=f"Test {role.value}",
            password_hash=hash_password(PASSWORD),
            role=role,
            institution_id=inst.id if role == Role.applicant else None,
        )
        db.add(user)
        created[role] = user
    db.commit()
    return created


@pytest.fixture()
def client(db, users):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_header(client):
    """auth_header(Role.admin) -> {"Authorization": "Bearer ..."}"""

    def _header(role: Role) -> dict[str, str]:
        res = client.post("/api/auth/login", json={"email": f"{role.value}@test.local", "password": PASSWORD})
        assert res.status_code == 200, res.text
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    return _header
