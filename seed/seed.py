"""Seed the database with SYNTHETIC demo data.

- 25 fictional institutions (mock institute records incl. TER payment / deficiency status)
- one demo user per role, plus one applicant per scenario institution
- ~12 applications in different states, built through the real services
  (upload -> extraction -> validation), from documents made by seed/generate_docs.py

Run from the repo root (with the backend venv):
    python seed/seed.py           # create tables, add anything missing (safe to re-run)
    python seed/seed.py --reset   # drop everything first, regenerate documents (clean demo start)
"""
import argparse
import json
import shutil
import sys
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import func, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import SessionLocal, create_all, drop_all  # noqa: E402
from app.enums import ApplicationCategory, Role  # noqa: E402
from app.models import Application, Finding, Institution, User  # noqa: E402
from app.services import applications as app_svc  # noqa: E402
from app.services import alerts, audit  # noqa: E402
from app.services.extraction.words import ocr_available  # noqa: E402
from app.services.verification import verify_application  # noqa: E402
from app.services.auth import hash_password  # noqa: E402
from app.services.documents import upload_document  # noqa: E402
from app.services.rules.loader import get_checklist, get_rule_set  # noqa: E402
from app.services.validation import latest_run, run_validation  # noqa: E402
from seed.data import DEMO_INSTITUTION, build_institutions  # noqa: E402
from seed.generate_docs import OUTPUT_DIR, generate_all  # noqa: E402

# Demo-only password for SYNTHETIC accounts. Not a secret; never reuse elsewhere.
DEMO_PASSWORD = "demo1234"

DEMO_USERS = [
    ("applicant@validex.demo", "Demo Applicant (SYNTHETIC)", Role.applicant),
    ("officer@validex.demo", "Demo Scrutiny Officer", Role.scrutiny_officer),
    ("senior@validex.demo", "Demo Senior Authority", Role.senior_authority),
    ("inspector@validex.demo", "Demo Inspector", Role.inspector),
    ("admin@validex.demo", "Demo Admin", Role.admin),
]


def _get_or_create_institution(db, data: dict) -> Institution:
    inst = db.execute(select(Institution).where(Institution.aicte_ref == data["aicte_ref"])).scalar_one_or_none()
    if inst is None:
        inst = Institution(**data)
        db.add(inst)
        db.flush()
        audit.log(db, audit.SYSTEM_ACTOR, "institution.seeded", "institution", inst.id,
                  {"name": inst.name, "synthetic": True})
    return inst


def _get_or_create_user(db, email: str, name: str, role: Role, institution_id: str | None,
                        password_hash: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(email=email, name=name, role=role, password_hash=password_hash,
                    institution_id=institution_id)
        db.add(user)
        db.flush()
        audit.log(db, audit.SYSTEM_ACTOR, "user.seeded", "user", user.id, {"role": role.value})
    return user


def seed_users_and_demo_institution() -> None:
    """Demo institution + one user per role + rule/checklist versions. Idempotent."""
    db = SessionLocal()
    try:
        inst = _get_or_create_institution(db, DEMO_INSTITUTION)
        pw = hash_password(DEMO_PASSWORD)
        for email, name, role in DEMO_USERS:
            _get_or_create_user(db, email, name, role, inst.id if role == Role.applicant else None, pw)
        get_rule_set(db)
        for category in ApplicationCategory:
            get_checklist(db, category.value)
        db.commit()
    finally:
        db.close()


def _drive_to_target(db, app: Application, spec: dict, applicant: User, officer: User) -> None:
    """Move a seeded application to its scenario status using the real workflow services."""
    target = spec["target_status"]
    if target == "draft":
        run_validation(db, applicant, app, precheck=True)
        return
    app_svc.submit(db, applicant, app)
    for req in verify_application(db, app, applicant.id):
        if spec.get("backdate_pending_hours") and req.status.value == "pending":
            req.requested_at = req.requested_at - timedelta(hours=spec["backdate_pending_hours"])
    run_validation(db, applicant, app, precheck=False, skip_permission=True)
    if target == "submitted":
        return
    app_svc.start_scrutiny(db, officer, app)
    run = latest_run(db, app, include_precheck=False)
    reasons = {
        "escalated": ("escalate", "Certificate number format needs senior review (demo)"),
        "returned_for_correction": ("return_for_correction", "Fire NOC has expired; upload a renewed NOC (demo)"),
        "scrutiny_complete": ("mark_scrutiny_complete", "All checks reviewed, nothing open (demo)"),
    }
    if target in reasons:
        decision, reason = reasons[target]
        app_svc.decide(db, officer, app, decision, reason, run.id)


def seed_institutions_and_applications() -> list[dict]:
    """All synthetic institutions plus scenario applications (only if no applications exist yet)."""
    db = SessionLocal()
    results = []
    try:
        institutions = [_get_or_create_institution(db, data) for data in build_institutions()]
        if db.scalar(select(func.count()).select_from(Application)):
            db.commit()
            return results

        manifest_path = OUTPUT_DIR / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else generate_all()
        by_ref = {i.aicte_ref: i for i in institutions}
        officer = db.execute(select(User).where(User.email == "officer@validex.demo")).scalar_one()
        pw = hash_password(DEMO_PASSWORD)

        for n, spec in enumerate(manifest["applications"], start=1):
            inst = by_ref[spec["institution_ref"]]
            applicant = _get_or_create_user(db, f"applicant{n}@validex.demo", f"Applicant {n} (SYNTHETIC)",
                                            Role.applicant, inst.id, pw)
            app = app_svc.create_application(db, applicant, ApplicationCategory(spec["category"]),
                                             "2027-28", spec["form_data"])
            for doc in spec["documents"]:
                data = (OUTPUT_DIR / doc["file"]).read_bytes()
                upload_document(db, applicant, app, doc["doc_type"], Path(doc["file"]).name, data)
            _drive_to_target(db, app, spec, applicant, officer)
            db.commit()
            results.append({"scenario": spec["scenario"], "app": app, "expected": spec["expected_rule_ids"],
                            "needs_ocr": spec.get("needs_ocr", False)})
        alerts.pending_verifications(db)
        db.commit()
        return results
    finally:
        db.close()


def _report(results: list[dict]) -> None:
    """Print expected vs actual rule ids so seed problems are visible immediately."""
    if not results:
        return
    db = SessionLocal()
    try:
        print("\nScenario check (expected rule ids vs actual, info severity ignored):")
        for r in results:
            run = latest_run(db, r["app"], include_precheck=True)
            actual = sorted({f.rule_id for f in db.execute(select(Finding).where(
                Finding.validation_run_id == run.id)).scalars() if f.severity.value != "info"})
            if r["needs_ocr"] and not ocr_available():
                print(f"  [skip] {r['scenario']:34} needs Tesseract (OCR); run in Docker for the full result")
                continue
            mark = "ok  " if actual == sorted(r["expected"]) else "DIFF"
            print(f"  [{mark}] {r['scenario']:34} expected={sorted(r['expected'])} actual={actual} "
                  f"incomplete={len(run.incomplete_checks)}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop all tables, files and generated docs first")
    args = parser.parse_args()
    if args.reset:
        drop_all()
        shutil.rmtree(settings.storage_dir, ignore_errors=True)
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    create_all()
    seed_users_and_demo_institution()
    results = seed_institutions_and_applications()
    _report(results)
    print(f"\nSeeded SYNTHETIC data. Demo password for all users: {DEMO_PASSWORD}")
    for email, _, role in DEMO_USERS:
        print(f"  {role.value:18} {email}")
    print(f"Demo upload files: {OUTPUT_DIR / 'demo_upload'}")


if __name__ == "__main__":
    main()
