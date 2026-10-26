from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Application, ApplicationDocument, ExtractedField, User
from app.routes.applications import load_application
from app.schemas import DocumentOut, ExtractedFieldOut, FieldCorrection, FileLinkOut
from app.services import documents as svc
from app.services import storage
from app.services.access import ensure_view

router = APIRouter(tags=["documents"])


def load_document(db: Session, document_id: str) -> tuple[ApplicationDocument, Application]:
    doc = db.get(ApplicationDocument, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc, db.get(Application, doc.application_id)


@router.post("/api/applications/{application_id}/documents", response_model=DocumentOut, status_code=201)
async def upload(application_id: str, doc_type: str = Form(...), file: UploadFile = File(...),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ApplicationDocument:
    app = load_application(db, application_id)
    # Read at most limit+1 bytes so oversized uploads are rejected without loading them fully.
    data = await file.read(settings.max_upload_bytes + 1)
    doc = svc.upload_document(db, user, app, doc_type, file.filename or "upload", data)
    db.commit()
    return doc


@router.get("/api/applications/{application_id}/documents", response_model=list[DocumentOut])
def list_documents(application_id: str, include_history: bool = False, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> list[ApplicationDocument]:
    app = load_application(db, application_id)
    ensure_view(user, app)
    query = select(ApplicationDocument).where(ApplicationDocument.application_id == app.id)
    if not include_history:
        query = query.where(ApplicationDocument.is_current)
    return list(db.execute(query.order_by(ApplicationDocument.uploaded_at)).scalars())


@router.get("/api/documents/{document_id}/fields", response_model=list[ExtractedFieldOut])
def fields(document_id: str, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)) -> list[ExtractedField]:
    doc, app = load_document(db, document_id)
    ensure_view(user, app)
    return svc.get_fields(db, doc)


@router.post("/api/documents/{document_id}/link", response_model=FileLinkOut)
def link(document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """Short-lived link to view the file. The token is the only credential the file URL needs."""
    doc, app = load_document(db, document_id)
    token = svc.issue_file_link(db, user, app, doc)
    db.commit()
    return {"url": f"/api/files/{token}", "expires_in_seconds": settings.file_link_expire_seconds}


@router.get("/api/files/{token}", include_in_schema=False)
def serve_file(token: str, db: Session = Depends(get_db)) -> FileResponse:
    claims = storage.read_file_token(token)
    if claims is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Link expired or invalid")
    doc = db.get(ApplicationDocument, claims["doc"])
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return FileResponse(storage.full_path(doc.storage_path), media_type=doc.mime_type,
                        headers={"Cache-Control": "no-store",
                                 "Content-Disposition": "inline"})


@router.patch("/api/fields/{field_id}", response_model=ExtractedFieldOut)
def correct(field_id: str, body: FieldCorrection, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)) -> ExtractedField:
    field = db.get(ExtractedField, field_id)
    if field is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found")
    _, app = load_document(db, field.document_id)
    ensure_view(user, app)
    svc.correct_field(db, user, field, body.value, body.reason)
    db.commit()
    return field
