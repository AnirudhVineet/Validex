"""Pydantic API schemas. These are the shared contracts exported to docs/schemas/."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums import (
    ApplicationCategory,
    ApplicationStatus,
    ExtractionSource,
    FindingCategory,
    FindingStatus,
    Role,
    Severity,
    VerificationStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Auth / users ----
class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1)


class UserOut(ORMModel):
    id: str
    email: str
    name: str
    role: Role
    institution_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class InstitutionOut(ORMModel):
    id: str
    name: str
    address: str
    state: str
    aicte_ref: str
    prior_eoa_year: int | None
    approved_intake: int
    faculty_count: int
    deficiency_status: str
    ter_payment_status: str
    is_synthetic: bool


# ---- Applications ----
class ApplicationOut(ORMModel):
    id: str
    institution_id: str
    category: ApplicationCategory
    academic_year: str
    status: ApplicationStatus
    current_version: int
    created_at: datetime
    submitted_at: datetime | None


# ---- Extraction / findings ----
class Evidence(BaseModel):
    page: int | None = None
    bbox: list[float] | None = Field(default=None, description="[x0, y0, x1, y1] in PDF points")
    snippet: str | None = None


class ExtractedFieldOut(ORMModel):
    id: str
    document_id: str
    field_name: str
    value: str | None
    confidence: float
    page: int | None
    bbox: list[float] | None
    source: ExtractionSource
    needs_confirmation: bool


class FindingOut(ORMModel):
    id: str
    application_id: str
    document_id: str | None
    validation_run_id: str
    rule_id: str
    rule_version: str
    category: FindingCategory
    severity: Severity
    title: str
    found_value: str | None
    expected_value: str | None
    evidence: Evidence | None
    explanation: str
    suggested_action: str
    status: FindingStatus
    visible_to_applicant: bool
    created_at: datetime
    reviewed_by: str | None
    review_reason: str | None


class FieldMismatch(BaseModel):
    field: str
    submitted: str | None
    source: str | None


class VerificationResultOut(ORMModel):
    source: str
    is_mock: bool
    reference_submitted: str
    requested_at: datetime
    status: VerificationStatus
    submitted_values: dict
    source_values: dict
    mismatches: list[FieldMismatch]
    error: str | None


# ---- Audit ----
class AuditEventOut(ORMModel):
    id: int
    actor: str
    event_type: str
    target_type: str
    target_id: str
    payload: dict
    timestamp: datetime
    prev_hash: str
    hash: str


class ChainVerifyResult(BaseModel):
    valid: bool
    events_checked: int
    first_bad_event_id: int | None = None
    reason: str | None = None


# ---- Dashboard ----
class DashboardSummary(BaseModel):
    role: Role
    counts: dict[str, int]
    notes: list[str] = []


# Schemas exported to docs/schemas/*.json
EXPORTED_SCHEMAS: list[type[BaseModel]] = [
    LoginRequest, TokenResponse, UserOut, InstitutionOut, ApplicationOut,
    Evidence, ExtractedFieldOut, FindingOut, VerificationResultOut,
    AuditEventOut, ChainVerifyResult, DashboardSummary,
]
