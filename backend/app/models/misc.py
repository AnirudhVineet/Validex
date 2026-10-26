from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import id_column, utcnow


class InspectionRecord(Base):
    __tablename__ = "inspection_records"

    id: Mapped[str] = id_column()
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    inspector_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str] = mapped_column(Text, default="")
    evidence_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("application_documents.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = id_column()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    application_id: Mapped[str | None] = mapped_column(ForeignKey("applications.id"), nullable=True)
    # missing | expired | pending_verification | anomaly | awaiting_correction
    kind: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(nullable=True)
