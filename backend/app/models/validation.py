from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.enums import FindingCategory, FindingStatus, RuleSetKind, Severity, VerificationStatus
from app.models.base import enum_column, id_column, utcnow


class RuleSetVersion(Base):
    """A versioned copy of a rules or checklist YAML file. Never edited in place."""

    __tablename__ = "rule_set_versions"

    id: Mapped[str] = id_column()
    kind: Mapped[RuleSetKind] = enum_column(RuleSetKind)
    name: Mapped[str] = mapped_column(String(100))  # e.g. "core" or "eoa_no_change"
    version: Mapped[int] = mapped_column(Integer)
    content_yaml: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[str] = id_column()
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    application_version: Mapped[int] = mapped_column(Integer)
    rule_set_version: Mapped[str] = mapped_column(String(50))
    checklist_version: Mapped[str] = mapped_column(String(50))
    is_precheck: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | completed | failed
    incomplete_checks: Mapped[list] = mapped_column(JSON, default=list)
    started_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = id_column()
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("application_documents.id"), nullable=True)
    validation_run_id: Mapped[str] = mapped_column(ForeignKey("validation_runs.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(50))
    rule_version: Mapped[str] = mapped_column(String(20))
    category: Mapped[FindingCategory] = enum_column(FindingCategory)
    severity: Mapped[Severity] = enum_column(Severity)
    title: Mapped[str] = mapped_column(String(255))
    found_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {page, bbox, snippet}
    explanation: Mapped[str] = mapped_column(Text)
    suggested_action: Mapped[str] = mapped_column(Text)
    status: Mapped[FindingStatus] = enum_column(FindingStatus, default=FindingStatus.open)
    visible_to_applicant: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class VerificationRequest(Base):
    __tablename__ = "verification_requests"

    id: Mapped[str] = id_column()
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("application_documents.id"), index=True)
    source: Mapped[str] = mapped_column(String(255))
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)
    reference_submitted: Mapped[str] = mapped_column(String(255))
    requested_at: Mapped[datetime] = mapped_column(default=utcnow)
    status: Mapped[VerificationStatus] = enum_column(VerificationStatus, default=VerificationStatus.pending)
    submitted_values: Mapped[dict] = mapped_column(JSON, default=dict)
    source_values: Mapped[dict] = mapped_column(JSON, default=dict)
    mismatches: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReviewAction(Base):
    """An officer / senior action on a finding or an application. Reason is required."""

    __tablename__ = "review_actions"

    id: Mapped[str] = id_column()
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    target_type: Mapped[str] = mapped_column(String(20))  # finding | application
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
