"""Shared enums. Must match docs/CONTRACTS.md."""
from enum import Enum


class Role(str, Enum):
    applicant = "applicant"
    scrutiny_officer = "scrutiny_officer"
    senior_authority = "senior_authority"
    inspector = "inspector"
    admin = "admin"


class ApplicationStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    under_scrutiny = "under_scrutiny"
    returned_for_correction = "returned_for_correction"
    escalated = "escalated"
    scrutiny_complete = "scrutiny_complete"


class ApplicationCategory(str, Enum):
    eoa_no_change = "eoa_no_change"
    eoa_increase_intake = "eoa_increase_intake"


class DocumentStatus(str, Enum):
    uploaded = "uploaded"
    processing = "processing"
    extracted = "extracted"
    failed = "failed"


class VerificationStatus(str, Enum):
    verified = "verified"
    mismatch = "mismatch"
    expired = "expired"
    pending = "pending"
    source_unavailable = "source_unavailable"
    manual_review = "manual_review"


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class FindingStatus(str, Enum):
    open = "open"
    resolved = "resolved"
    dismissed = "dismissed"
    escalated = "escalated"


class FindingCategory(str, Enum):
    completeness = "completeness"
    expiry = "expiry"
    consistency = "consistency"
    anomaly = "anomaly"
    verification = "verification"
    infrastructure = "infrastructure"


class ExtractionSource(str, Enum):
    pdf_text = "pdf_text"
    ocr = "ocr"
    manual = "manual"


class RuleSetKind(str, Enum):
    rules = "rules"
    checklist = "checklist"


# Roles that may see the full (unfiltered) validation report.
STAFF_ROLES = (Role.scrutiny_officer, Role.senior_authority, Role.admin)
