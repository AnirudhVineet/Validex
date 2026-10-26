from sqlalchemy import select, text

from app.enums import Role
from app.models import AuditEvent
from app.services import audit


def _write_events(db, n=3):
    for i in range(n):
        audit.log(db, "system", "test.event", "thing", f"t{i}", {"i": i, "note": "hello"})
    db.commit()


def test_empty_chain_is_valid(db):
    assert audit.verify_chain(db)["valid"] is True


def test_chain_links_events(db):
    _write_events(db)
    events = db.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars().all()
    assert events[0].prev_hash == audit.GENESIS_HASH
    assert events[1].prev_hash == events[0].hash
    assert audit.verify_chain(db) == {
        "valid": True, "events_checked": 3, "first_bad_event_id": None, "reason": None
    }


def test_tampered_payload_is_detected(db):
    _write_events(db)
    second = db.execute(select(AuditEvent).order_by(AuditEvent.id).offset(1).limit(1)).scalar_one()
    # Tamper directly in SQL, bypassing the ORM, as an attacker with DB access would.
    db.execute(text("UPDATE audit_events SET payload = :p WHERE id = :id"),
               {"p": '{"i": 99, "note": "hello"}', "id": second.id})
    db.commit()
    db.expire_all()
    result = audit.verify_chain(db)
    assert result["valid"] is False
    assert result["first_bad_event_id"] == second.id


def test_deleted_row_is_detected(db):
    _write_events(db)
    first = db.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars().first()
    db.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": first.id})
    db.commit()
    db.expire_all()
    assert audit.verify_chain(db)["valid"] is False


def test_mask_keeps_last_four():
    assert audit.mask("ABCD123456") == "******3456"
    assert audit.mask("abc") == "***"
    assert audit.mask(None) is None


def test_login_writes_audit_event(client, db):
    client.post("/api/auth/login", json={"email": "admin@test.local", "password": "test-pass"})
    types = [e.event_type for e in db.execute(select(AuditEvent)).scalars()]
    assert "user.login" in types


def test_verify_endpoint(client, auth_header):
    res = client.get("/api/audit/verify", headers=auth_header(Role.admin))
    assert res.status_code == 200
    assert res.json()["valid"] is True
