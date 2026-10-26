"""Review-priority score: a transparent ordering aid for the scrutiny queue.

It is a weighted count of open issues with every factor shown. It is NOT a probability of
anything and says nothing about whether an institution is compliant. Hidden from applicants.
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import FindingCategory, FindingStatus, Severity
from app.models import Application, Finding
from app.models.base import utcnow
from app.services.validation import latest_run

SEVERITY_POINTS = {Severity.critical: 25, Severity.high: 12, Severity.medium: 5, Severity.low: 2, Severity.info: 0}
ANOMALY_BONUS = 8          # per open anomaly indicator, on top of its severity points
VERIFICATION_BONUS = 6     # per open verification finding (mismatch, unavailable, ...)
INCOMPLETE_POINTS = 3      # per document whose checks could not complete
WAITING_POINTS_PER_DAY = 1
WAITING_CAP = 10
MAX_SCORE = 100
DESCRIPTION = ("Review-priority aid: higher means more open issues to look at first. "
               "Not a probability and not a compliance judgement.")


def compute(db: Session, app: Application, now: datetime | None = None) -> dict:
    """{score, max, description, factors: [{factor, points, detail}]} from the latest official run."""
    run = latest_run(db, app, include_precheck=False)
    factors: list[dict] = []
    if run is not None:
        open_findings = list(db.execute(select(Finding).where(
            Finding.validation_run_id == run.id, Finding.status == FindingStatus.open)).scalars())
        for sev in Severity:
            n = sum(1 for f in open_findings if f.severity == sev)
            if n and SEVERITY_POINTS[sev]:
                factors.append({"factor": f"open {sev.value} findings", "points": n * SEVERITY_POINTS[sev],
                                "detail": f"{n} x {SEVERITY_POINTS[sev]}"})
        anomalies = sum(1 for f in open_findings if f.category == FindingCategory.anomaly)
        if anomalies:
            factors.append({"factor": "preliminary anomaly indicators", "points": anomalies * ANOMALY_BONUS,
                            "detail": f"{anomalies} x {ANOMALY_BONUS}"})
        verification = sum(1 for f in open_findings if f.category == FindingCategory.verification
                           and f.severity != Severity.info)
        if verification:
            factors.append({"factor": "issuer verification issues", "points": verification * VERIFICATION_BONUS,
                            "detail": f"{verification} x {VERIFICATION_BONUS}"})
        incomplete_docs = {c.get("document_id") or c.get("rule_id") for c in run.incomplete_checks or []}
        if incomplete_docs:
            factors.append({"factor": "checks that could not complete", "points": len(incomplete_docs) * INCOMPLETE_POINTS,
                            "detail": f"{len(incomplete_docs)} document(s) x {INCOMPLETE_POINTS}"})
    if app.submitted_at is not None:
        days = max(0, ((now or utcnow()) - app.submitted_at).days)
        if days:
            factors.append({"factor": "days since submission", "points": min(WAITING_CAP, days * WAITING_POINTS_PER_DAY),
                            "detail": f"{days} day(s), capped at {WAITING_CAP}"})
    raw = sum(f["points"] for f in factors)
    return {"score": min(MAX_SCORE, raw), "max": MAX_SCORE, "raw_points": raw,
            "description": DESCRIPTION, "factors": factors}
