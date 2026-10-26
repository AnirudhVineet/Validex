"""Pydantic API schemas. These are the shared contracts exported to docs/schemas/."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums import (
    ApplicationCategory,
    ApplicationStatus,
    DocumentStatus,
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
class ApplicationCreate(BaseModel):
    category: ApplicationCategory
    academic_year: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}$", examples=["2027-28"])
    form_data: dict = Field(default_factory=dict)


class ApplicationUpdate(BaseModel):
    form_data: dict


class ApplicationOut(ORMModel):
    id: str
    institution_id: str
    category: ApplicationCategory
    academic_year: str
    status: ApplicationStatus
    current_version: int
    form_data: dict
    created_at: datetime
    submitted_at: datetime | None
    updated_at: datetime


class ApplicationListItem(ApplicationOut):
    institution_name: str
    open_findings: int = 0
    critical_findings: int = 0
    priority_score: int | None = None


class ApplicationVersionOut(ORMModel):
    version: int
    submitted_by: str
    submitted_at: datetime
    snapshot: dict


class ChecklistItemOut(BaseModel):
    doc_type: str
    label: str
    description: str
    requirement: str = Field(description="required | optional (after resolving conditionals)")
    configured_as: str = Field(description="required | optional | conditional")
    reason: str
    condition_unresolved: bool
    document_id: str | None
    document_status: str | None
    uploaded: bool


class DocumentOut(ORMModel):
    id: str
    application_id: str
    version: int
    doc_type: str
    original_filename: str
    sha256: str
    size_bytes: int
    mime_type: str
    status: DocumentStatus
    is_current: bool
    classified_type: str | None
    extraction_method: str | None
    extraction_error: str | None
    uploaded_at: datetime


class FileLinkOut(BaseModel):
    url: str
    expires_in_seconds: int
    page_url_template: str = Field(description="Replace {page} with a 1-based page number to get a PNG")
    pages: int
    page_scale: float = Field(description="PNG pixels per bbox unit (PDF points, or pixels for images)")


class FieldCorrection(BaseModel):
    value: str = Field(min_length=1)
    reason: str = Field(min_length=5)


class ReviewRequest(BaseModel):
    action: str = Field(description="resolve | dismiss | escalate")
    reason: str = Field(min_length=5)


class DecisionRequest(BaseModel):
    decision: str = Field(description="mark_scrutiny_complete | return_for_correction | escalate")
    reason: str = Field(min_length=5)


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


class IncompleteCheck(BaseModel):
    rule_id: str
    document_id: str | None
    doc_type: str | None
    reason: str


class ValidationRunOut(ORMModel):
    id: str
    application_id: str
    application_version: int
    rule_set_version: str
    checklist_version: str
    is_precheck: bool
    status: str
    incomplete_checks: list[IncompleteCheck]
    started_by: str
    started_at: datetime
    finished_at: datetime | None


class ReportDocument(BaseModel):
    id: str
    doc_type: str
    original_filename: str
    status: str
    sha256: str
    uploaded_at: datetime
    classified_type: str | None
    extraction_method: str | None
    extraction_error: str | None
    fields: list[ExtractedFieldOut]


class ReportOut(BaseModel):
    application: ApplicationOut
    institution: InstitutionOut
    run: ValidationRunOut | None
    summary: dict[str, int]
    findings: list[FindingOut]
    incomplete_checks: list[IncompleteCheck]
    checklist: list[ChecklistItemOut]
    missing_form_fields: list[str]
    documents: list[ReportDocument]
    rules: "dict[str, RuleInfo]" = Field(description="What each rule in this run checks (explainability)")
    verifications: "list[VerificationOut]" = Field(default_factory=list, description="Staff only; empty for applicants")
    priority: "PriorityOut | None" = Field(default=None, description="Staff only")
    disclaimer: str


class VerificationOut(VerificationResultOut):
    id: str
    document_id: str
    doc_type: str


class PriorityFactor(BaseModel):
    factor: str
    points: int
    detail: str


class PriorityOut(BaseModel):
    score: int
    max: int
    raw_points: int
    description: str
    factors: list[PriorityFactor]


class NotificationOut(ORMModel):
    id: str
    application_id: str | None
    kind: str
    message: str
    created_at: datetime
    read_at: datetime | None


class RuleSetVersionOut(ORMModel):
    id: str
    name: str
    version: int
    content_hash: str
    is_active: bool
    created_by: str | None
    created_at: datetime


class RuleSetDetail(RuleSetVersionOut):
    content_yaml: str


class RuleText(BaseModel):
    content_yaml: str = Field(min_length=1)


class RuleSave(RuleText):
    reason: str = Field(min_length=5)


class RuleValidation(BaseModel):
    valid: bool
    errors: list[str]
    rule_count: int


class RerunResult(BaseModel):
    rule_set_version: str
    applications_rerun: int


class RuleInfo(BaseModel):
    description: str
    category: FindingCategory
    check: str


class ExpiryItem(BaseModel):
    application_id: str
    institution: str
    doc_type: str
    expiry_date: str
    days_left: int
    status: str


class ExpiryForecast(BaseModel):
    window_days: int
    today: str
    expired: int
    items: list[ExpiryItem]


class CommonDeficiency(BaseModel):
    rule_id: str
    description: str
    applications: int


class SeniorOverview(BaseModel):
    status_counts: dict[str, int]
    ageing: dict[str, int]
    common_deficiencies: list[CommonDeficiency]
    open_applications: int


class TimeSaved(BaseModel):
    minutes: int
    hours: float
    inputs: dict[str, int]
    assumption: str


class InspectionOut(ORMModel):
    id: str
    application_id: str
    inspector_id: str
    notes: str
    evidence_document_id: str | None
    evidence_label: str | None
    created_at: datetime


class AdvisoryItem(BaseModel):
    key: str
    label: str
    evidence_files: int
    present: bool
    labels_read_from_evidence: list[str]


class InfrastructureAdvisory(BaseModel):
    notice: str
    illustrative: bool
    ocr_available: bool
    items: list[AdvisoryItem]


class LetterDraft(BaseModel):
    draft: bool
    text: str
    finding_ids: list[str]


class SummaryPoint(BaseModel):
    text: str
    finding_ids: list[str]


class CaseSummary(BaseModel):
    enabled: bool
    model: str | None
    insufficient_evidence: bool
    points: list[SummaryPoint]
    dropped_points: int
    note: str | None = None


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
    LoginRequest, TokenResponse, UserOut, InstitutionOut, ApplicationCreate, ApplicationUpdate,
    ApplicationOut, ApplicationListItem, ApplicationVersionOut, ChecklistItemOut, DocumentOut,
    FileLinkOut, FieldCorrection, ReviewRequest, DecisionRequest, Evidence, ExtractedFieldOut,
    FindingOut, IncompleteCheck, ValidationRunOut, ReportOut, VerificationResultOut, VerificationOut,
    PriorityOut, NotificationOut, RuleSetVersionOut, RuleSetDetail, RuleText, RuleSave, RuleValidation,
    RerunResult, RuleInfo, ExpiryForecast, SeniorOverview, TimeSaved, InspectionOut, InfrastructureAdvisory,
    LetterDraft, CaseSummary,
    AuditEventOut, ChainVerifyResult, DashboardSummary,
]
ReportOut.model_rebuild()
