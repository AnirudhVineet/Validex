from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.enums import ApplicationCategory, ApplicationStatus, DocumentStatus, ExtractionSource
from app.models.base import enum_column, id_column, utcnow


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = id_column()
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    category: Mapped[ApplicationCategory] = enum_column(ApplicationCategory)
    academic_year: Mapped[str] = mapped_column(String(20))
    status: Mapped[ApplicationStatus] = enum_column(ApplicationStatus, default=ApplicationStatus.draft)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class ApplicationVersion(Base):
    """Snapshot taken at every submit / resubmit (version history)."""

    __tablename__ = "application_versions"

    id: Mapped[str] = id_column()
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    submitted_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime] = mapped_column(default=utcnow)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)


class ApplicationDocument(Base):
    __tablename__ = "application_documents"

    id: Mapped[str] = id_column()
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    doc_type: Mapped[str] = mapped_column(String(50))
    original_filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(100))
    storage_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[DocumentStatus] = enum_column(DocumentStatus, default=DocumentStatus.uploaded)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(default=utcnow)


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[str] = id_column()
    document_id: Mapped[str] = mapped_column(ForeignKey("application_documents.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(100))
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [x0, y0, x1, y1]
    source: Mapped[ExtractionSource] = enum_column(ExtractionSource)
    needs_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    corrected_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    corrected_at: Mapped[datetime | None] = mapped_column(nullable=True)
