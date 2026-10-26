"""Cross-application intelligence: the same file, certificate number or faculty IDs showing up
in another institution's application.

Only other institutions are compared (an institution's own resubmissions and earlier years are
expected to repeat documents), and only applications that have been submitted at least once.
Matches become preliminary anomaly indicators for officers; they may have a legitimate
explanation (shared campus land, faculty who moved, a consultant's template).
"""
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, ApplicationDocument, ExtractedField, Institution
from app.services.applications import INSPECTION_DOC_TYPE


def _other_documents(db: Session, app: Application) -> list[tuple[ApplicationDocument, Application, Institution]]:
    rows = db.execute(
        select(ApplicationDocument, Application, Institution)
        .join(Application, ApplicationDocument.application_id == Application.id)
        .join(Institution, Application.institution_id == Institution.id)
        .where(ApplicationDocument.is_current, Application.institution_id != app.institution_id,
               Application.submitted_at.is_not(None), ApplicationDocument.doc_type != INSPECTION_DOC_TYPE)
    ).all()
    return [tuple(r) for r in rows]


def _field_values(db: Session, doc_ids: list[str], name: str) -> dict[str, str]:
    if not doc_ids:
        return {}
    rows = db.execute(select(ExtractedField.document_id, ExtractedField.value).where(
        ExtractedField.document_id.in_(doc_ids), ExtractedField.field_name == name)).all()
    return {doc_id: value for doc_id, value in rows if value}


def find_matches(db: Session, app: Application, docs: list[ApplicationDocument]) -> dict[str, list[dict]]:
    """document id -> [{kind, other_institution, other_application_id, other_doc_type, detail}]"""
    others = _other_documents(db, app)
    if not others or not docs:
        return {}
    other_ids = [d.id for d, _, _ in others]
    other_certs = _field_values(db, other_ids, "certificate_number")
    other_faculty = _field_values(db, other_ids, "faculty_ids")
    mine_certs = _field_values(db, [d.id for d in docs], "certificate_number")
    mine_faculty = _field_values(db, [d.id for d in docs], "faculty_ids")

    matches: dict[str, list[dict]] = defaultdict(list)
    for doc in docs:
        for other, other_app, inst in others:
            base = {"other_institution": inst.name, "other_application_id": other_app.id,
                    "other_doc_type": other.doc_type}
            if doc.sha256 == other.sha256:
                matches[doc.id].append({**base, "kind": "same_file", "detail": f"SHA-256 {doc.sha256[:16]}..."})
            cert = mine_certs.get(doc.id)
            if cert and other_certs.get(other.id, "").upper() == cert.upper():
                matches[doc.id].append({**base, "kind": "certificate_number", "detail": cert})
            mine = set(filter(None, mine_faculty.get(doc.id, "").split(",")))
            theirs = set(filter(None, other_faculty.get(other.id, "").split(",")))
            shared = sorted(mine & theirs)
            if shared:
                matches[doc.id].append({**base, "kind": "faculty_ids", "detail": ",".join(shared),
                                        "count": len(shared)})
    return dict(matches)
