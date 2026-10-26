"""Hash-chained audit log.

Every important write calls `log()` inside the same DB transaction as the change itself,
so the change and its audit event commit (or roll back) together.

The chain is tamper-EVIDENT, not immutable: anyone with DB access can edit rows, but
`verify_chain()` will then report the first event whose hash no longer matches.

Concurrency note (prototype): on PostgreSQL we take a transaction-level advisory lock so two
writers cannot both chain onto the same previous hash. On SQLite the dev server is a single
process and SQLite serialises writers; a fork in the chain would still be caught by verify_chain().
"""
import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.models.base import utcnow

GENESIS_HASH = "0" * 64
_PG_LOCK_KEY = 815_001  # arbitrary constant for pg_advisory_xact_lock
SYSTEM_ACTOR = "system"


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _format_ts(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def compute_hash(prev_hash: str, actor: str, event_type: str, target_type: str,
                 target_id: str, payload: dict, timestamp: datetime) -> str:
    """sha256(prev_hash + canonical JSON of the event body). See docs/CONTRACTS.md."""
    body = _canonical_json({
        "actor": actor,
        "event_type": event_type,
        "target_type": target_type,
        "target_id": target_id,
        "payload": payload,
        "timestamp": _format_ts(timestamp),
    })
    return hashlib.sha256((prev_hash + body).encode("utf-8")).hexdigest()


def mask(value: str | None, keep: int = 4) -> str | None:
    """Mask an identifier or personal field for logs: 'ABCD1234' -> '****1234'."""
    if value is None:
        return None
    value = str(value)
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * (len(value) - keep) + value[-keep:]


def log(db: Session, actor: str, event_type: str, target_type: str, target_id: str,
        payload: dict | None = None) -> AuditEvent:
    """Append an audit event to the chain. Flushes but does NOT commit (caller commits)."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _PG_LOCK_KEY})

    last = db.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)).scalar_one_or_none()
    prev_hash = last.hash if last else GENESIS_HASH

    # Round-trip through JSON so what we hash is exactly what the DB will store.
    clean_payload = json.loads(_canonical_json(payload or {}))
    timestamp = utcnow()
    event = AuditEvent(
        actor=str(actor),
        event_type=event_type,
        target_type=target_type,
        target_id=str(target_id),
        payload=clean_payload,
        timestamp=timestamp,
        prev_hash=prev_hash,
        hash=compute_hash(prev_hash, str(actor), event_type, target_type, str(target_id),
                          clean_payload, timestamp),
    )
    db.add(event)
    db.flush()
    return event


def verify_chain(db: Session) -> dict:
    """Recompute every hash in order. Returns {valid, events_checked, first_bad_event_id, reason}."""
    events = db.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars().all()
    prev_hash = GENESIS_HASH
    for count, ev in enumerate(events, start=1):
        if ev.prev_hash != prev_hash:
            return {"valid": False, "events_checked": count, "first_bad_event_id": ev.id,
                    "reason": "prev_hash does not match previous event (row missing or reordered)"}
        expected = compute_hash(ev.prev_hash, ev.actor, ev.event_type, ev.target_type,
                                ev.target_id, ev.payload, ev.timestamp)
        if ev.hash != expected:
            return {"valid": False, "events_checked": count, "first_bad_event_id": ev.id,
                    "reason": "event content does not match its hash (row modified)"}
        prev_hash = ev.hash
    return {"valid": True, "events_checked": len(events), "first_bad_event_id": None, "reason": None}
