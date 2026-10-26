"""Shared fixtures: a fresh in-memory SQLite DB per test, one user per role, temp file storage."""
import random
import sys
from datetime import date
from pathlib import Path

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
from app.config import settings
from app.services.auth import hash_password

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for seed.docgen
from seed import docgen  # noqa: E402

PASSWORD = "test-pass"
PASSWORD_HASH = hash_password(PASSWORD)  # hash once; bcrypt is slow on purpose
INSTITUTION = {
    "name": "SYNTHETIC Test Institute of Engineering, Testpur",
    "address": "Survey No 7, Mock Road, Testpur, Sample State 000002",
    "state": "Sample State",
    "aicte_ref": "SYN-TEST-0001",
    "approved_intake": 120,
    "faculty_count": 12,
}


@pytest.fixture(autouse=True)
def temp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "files")


@pytest.fixture()
def make_pdf():
    """make_pdf("fire_noc", "expired") -> GeneratedDoc for the test institution, dated today."""

    def _make(doc_type: str, variant: str = "valid", seed: int = 1, **kwargs) -> docgen.GeneratedDoc:
        inst = docgen.InstitutionData(INSTITUTION["name"], INSTITUTION["address"], INSTITUTION["aicte_ref"],
                                      INSTITUTION["state"], INSTITUTION["faculty_count"])
        return docgen.make_document(doc_type, variant, inst, date.today(), random.Random(seed), **kwargs)

    return _make


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
    inst = Institution(**INSTITUTION)
    other = Institution(name="SYNTHETIC Other College, Elsewhere", aicte_ref="SYN-TEST-0002",
                        address="1 Other Street, Elsewhere")
    db.add_all([inst, other])
    db.flush()
    created = {}
    for role in Role:
        user = User(
            email=f"{role.value}@test.local",
            name=f"Test {role.value}",
            password_hash=PASSWORD_HASH,
            role=role,
            institution_id=inst.id if role == Role.applicant else None,
        )
        db.add(user)
        created[role] = user
    outsider = User(email="other_applicant@test.local", name="Other applicant",
                    password_hash=PASSWORD_HASH, role=Role.applicant, institution_id=other.id)
    db.add(outsider)
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

    def _header(role: Role | str) -> dict[str, str]:
        email = f"{role.value}@test.local" if isinstance(role, Role) else role
        res = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert res.status_code == 200, res.text
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    return _header
