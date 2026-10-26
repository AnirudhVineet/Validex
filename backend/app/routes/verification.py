from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.routes.applications import load_application
from app.routes.documents import load_document
from app.schemas import VerificationOut
from app.services.access import STAFF, ensure_reviewer, ensure_view
from app.services.validation import OFFICIAL_RUN_STATUSES, run_validation
from app.services.verification import latest_verifications, verify_document

router = APIRouter(tags=["verification"])


def _out(v, doc_type: str) -> dict:
    return {**{c: getattr(v, c) for c in (
        "id", "document_id", "source", "is_mock", "reference_submitted", "requested_at", "status",
        "submitted_values", "source_values", "mismatches", "error")}, "doc_type": doc_type}


@router.post("/api/documents/{document_id}/verify", response_model=VerificationOut)
def verify(document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """Ask the (MOCK) issuer again, then re-run official validation so findings reflect the result."""
    doc, app = load_document(db, document_id)
    ensure_view(user, app)
    ensure_reviewer(user)
    if app.status not in OFFICIAL_RUN_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Verification is not available while '{app.status.value}'")
    req = verify_document(db, doc, user.id)
    if req is None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"No issuer is configured for '{doc.doc_type}'")
    run_validation(db, user, app, precheck=False)
    db.commit()
    return _out(req, doc.doc_type)


@router.get("/api/applications/{application_id}/verifications", response_model=list[VerificationOut])
def list_verifications(application_id: str, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)) -> list[dict]:
    """Submitted value vs source value, per document. Staff only."""
    app = load_application(db, application_id)
    ensure_view(user, app)
    if user.role not in STAFF:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verification details are for scrutiny staff")
    from app.services.applications import current_documents

    types = {d.id: d.doc_type for d in current_documents(db, app)}
    return [_out(v, types[v.document_id]) for v in latest_verifications(db, app).values() if v.document_id in types]
