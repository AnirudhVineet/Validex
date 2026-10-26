"""Seed the database with SYNTHETIC demo data.

Phase 0: one synthetic institution and one user per role.
Phase 1 will extend this with ~25 institutions, applications and generated documents.

Run from the repo root (with the backend venv active):
    python seed/seed.py           # create tables and add missing seed rows
    python seed/seed.py --reset   # drop everything first (clean demo start)
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal, create_all, drop_all  # noqa: E402
from app.enums import Role  # noqa: E402
from app.models import Institution, User  # noqa: E402
from app.services import audit  # noqa: E402
from app.services.auth import hash_password  # noqa: E402

# Demo-only password for SYNTHETIC accounts. Not a secret; never reuse elsewhere.
DEMO_PASSWORD = "demo1234"

DEMO_INSTITUTION = {
    "name": "SYNTHETIC Institute of Technology, Demo Nagar",
    "address": "Plot 12, Fictional Industrial Area, Demo Nagar, Sample State 000001",
    "state": "Sample State",
    "aicte_ref": "SYN-1-0000000001",
    "prior_eoa_year": 2025,
    "approved_intake": 300,
    "faculty_count": 24,
    "deficiency_status": "none",
    "ter_payment_status": "paid",
    "is_synthetic": True,
}

DEMO_USERS = [
    ("applicant@validex.demo", "Demo Applicant (SYNTHETIC)", Role.applicant),
    ("officer@validex.demo", "Demo Scrutiny Officer", Role.scrutiny_officer),
    ("senior@validex.demo", "Demo Senior Authority", Role.senior_authority),
    ("inspector@validex.demo", "Demo Inspector", Role.inspector),
    ("admin@validex.demo", "Demo Admin", Role.admin),
]


def seed() -> None:
    db = SessionLocal()
    try:
        inst = db.execute(
            select(Institution).where(Institution.aicte_ref == DEMO_INSTITUTION["aicte_ref"])
        ).scalar_one_or_none()
        if inst is None:
            inst = Institution(**DEMO_INSTITUTION)
            db.add(inst)
            db.flush()
            audit.log(db, audit.SYSTEM_ACTOR, "institution.seeded", "institution", inst.id,
                      {"name": inst.name, "synthetic": True})

        for email, name, role in DEMO_USERS:
            if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
                continue
            user = User(
                email=email, name=name, role=role, password_hash=hash_password(DEMO_PASSWORD),
                institution_id=inst.id if role == Role.applicant else None,
            )
            db.add(user)
            db.flush()
            audit.log(db, audit.SYSTEM_ACTOR, "user.seeded", "user", user.id, {"role": role.value})
        db.commit()
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop all tables before seeding")
    args = parser.parse_args()
    if args.reset:
        drop_all()
    create_all()
    seed()
    print(f"Seeded SYNTHETIC data. Demo password for all users: {DEMO_PASSWORD}")
    for email, _, role in DEMO_USERS:
        print(f"  {role.value:18} {email}")


if __name__ == "__main__":
    main()
