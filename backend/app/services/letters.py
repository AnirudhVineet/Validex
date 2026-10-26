"""Template-based deficiency letter, drafted for an officer to review and edit. No LLM.

It only uses findings the applicant is allowed to see (never anomaly indicators, verification
details or the priority score), and it is always marked DRAFT until the officer sends it as
the reason of a "Return for correction" decision.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import FindingStatus, Severity
from app.models import Application, Finding, Institution, User
from app.services import audit
from app.services.access import ensure_reviewer
from app.services.validation import latest_run

TEMPLATE = """DRAFT - for officer review before sending

Date: {today}
To: {institution} ({reference})
Subject: Deficiencies found during scrutiny of the Extension of Approval application ({year})

The application submitted for {year} (version {version}) has been scrutinised. Please address
the following points and resubmit through the portal:

{points}

Automated checks assisted this scrutiny; each point above was reviewed by the scrutiny officer.
This letter is not an approval or rejection of the application.

Scrutiny Officer
(Validex prototype - SYNTHETIC data, not an official AICTE communication)
"""


def draft(db: Session, user: User, app: Application) -> dict:
    ensure_reviewer(user)
    run = latest_run(db, app, include_precheck=False)
    findings = []
    if run is not None:
        findings = list(db.execute(select(Finding).where(
            Finding.validation_run_id == run.id, Finding.visible_to_applicant.is_(True),
            Finding.status.in_([FindingStatus.open, FindingStatus.escalated]))).scalars())
        order = list(Severity)
        findings.sort(key=lambda f: (order.index(f.severity), f.rule_id))
    inst = db.get(Institution, app.institution_id)
    if findings:
        points = "\n".join(
            f"{i}. {f.title}.\n   Found: {f.found_value or '-'}; expected: {f.expected_value or '-'}.\n"
            f"   Action required: {f.suggested_action}"
            for i, f in enumerate(findings, start=1))
    else:
        points = "(No open applicant-visible findings. Add points manually if needed.)"
    text = TEMPLATE.format(today=date.today().isoformat(), institution=inst.name, reference=inst.aicte_ref,
                           year=app.academic_year, version=app.current_version, points=points)
    audit.log(db, user.id, "letter.drafted", "application", app.id,
              {"run_id": run.id if run else None, "finding_ids": [f.id for f in findings]})
    return {"draft": True, "text": text, "finding_ids": [f.id for f in findings]}
