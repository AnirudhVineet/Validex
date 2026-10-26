"""Optional evidence-grounded case summary (LLM). DISABLED by default.

- Never part of validation: it reads stored findings and writes nothing but an audit event.
- Grounded: the model sees only the findings list; every point must cite finding ids.
  Points citing unknown ids are dropped; if nothing valid remains the result is
  "insufficient evidence". The model may also say so itself.
- Anomaly findings are passed with their "preliminary indicator" wording and the prompt
  forbids stronger claims.
"""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Application, Finding, Institution, User
from app.services import audit
from app.services.validation import latest_run

SYSTEM = (
    "You summarise automated pre-validation findings for a government scrutiny officer. "
    "Use ONLY the findings provided. Every point must cite the ids of the findings it is based on. "
    "Do not add facts, do not guess, do not recommend approving or rejecting. Findings in the "
    "'anomaly' category are preliminary indicators that require manual review: describe them only "
    "that way and never as wrongdoing. If the findings are not enough for a useful summary, set "
    "insufficient_evidence to true and return no points."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "insufficient_evidence": {"type": "boolean"},
        "points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "finding_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "finding_ids"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["insufficient_evidence", "points"],
    "additionalProperties": False,
}


def _findings_payload(findings: list[Finding]) -> list[dict]:
    return [{"id": f.id, "rule_id": f.rule_id, "category": f.category.value, "severity": f.severity.value,
             "status": f.status.value, "title": f.title, "found": f.found_value, "expected": f.expected_value,
             "explanation": f.explanation} for f in findings]


def _call_model(findings_json: str) -> dict | None:
    """Call Claude with structured output. Returns the parsed JSON, or None on refusal."""
    import anthropic

    client = anthropic.Anthropic()  # credentials from the environment (ANTHROPIC_API_KEY, ...)
    response = client.beta.messages.create(
        model=settings.llm_model,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # retry on a fallback model if a safety classifier declines
        system=SYSTEM,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": f"Findings (JSON):\n{findings_json}"}],
    )
    if response.stop_reason == "refusal":
        return None
    text = next((b.text for b in response.content if b.type == "text"), "")
    return json.loads(text)


def ground(raw: dict | None, valid_ids: set[str]) -> dict:
    """Keep only points whose citations all refer to real findings."""
    if raw is None:
        return {"insufficient_evidence": True, "points": [], "dropped_points": 0, "note": "Model declined to answer."}
    kept, dropped = [], 0
    for point in raw.get("points", []):
        ids = [i for i in point.get("finding_ids", []) if isinstance(i, str)]
        if ids and all(i in valid_ids for i in ids) and point.get("text", "").strip():
            kept.append({"text": point["text"].strip(), "finding_ids": ids})
        else:
            dropped += 1
    insufficient = bool(raw.get("insufficient_evidence")) or not kept
    return {"insufficient_evidence": insufficient, "points": [] if insufficient else kept,
            "dropped_points": dropped, "note": None}


def summarize(db: Session, user: User, app: Application, caller=None) -> dict:
    """caller: injectable model call (tests); defaults to the real Claude call."""
    if not settings.llm_summary_enabled:
        return {"enabled": False, "insufficient_evidence": True, "points": [], "dropped_points": 0,
                "model": None, "note": "LLM summary is disabled (set LLM_SUMMARY_ENABLED=true to enable)."}
    run = latest_run(db, app, include_precheck=False)
    findings = list(db.execute(select(Finding).where(Finding.validation_run_id == run.id)).scalars()) if run else []
    if not findings:
        return {"enabled": True, "insufficient_evidence": True, "points": [], "dropped_points": 0,
                "model": settings.llm_model, "note": "No findings to summarise."}
    inst = db.get(Institution, app.institution_id)
    payload = json.dumps({"institution": inst.name, "findings": _findings_payload(findings)}, indent=1)
    try:
        raw = (caller or _call_model)(payload)
    except Exception as exc:  # noqa: BLE001 - the summary is optional; never break the page
        return {"enabled": True, "insufficient_evidence": True, "points": [], "dropped_points": 0,
                "model": settings.llm_model, "note": f"Summary unavailable ({type(exc).__name__})."}
    result = ground(raw, {f.id for f in findings})
    audit.log(db, user.id, "summary.generated", "application", app.id, {
        "model": settings.llm_model, "run_id": run.id, "points": len(result["points"]),
        "dropped_points": result["dropped_points"], "insufficient_evidence": result["insufficient_evidence"]})
    return {"enabled": True, "model": settings.llm_model, **result}
