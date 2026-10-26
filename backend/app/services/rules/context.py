"""Plain data objects the rule checks work on. Checks never touch the database directly."""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class FieldView:
    name: str
    value: str | None
    confidence: float
    page: int | None
    bbox: list[float] | None
    source: str
    needs_confirmation: bool

    def evidence(self) -> dict:
        return {"page": self.page, "bbox": self.bbox, "snippet": self.value}


@dataclass
class DocView:
    id: str
    doc_type: str
    status: str
    classified_type: str | None
    extraction_error: str | None
    fields: dict[str, FieldView] = field(default_factory=dict)
    sha256: str = ""
    analysis: dict = field(default_factory=dict)

    @property
    def qr_ref(self) -> str | None:
        refs = [q.get("ref") for q in self.analysis.get("qr", []) if q.get("ref")]
        return refs[0] if refs else None

    @property
    def extracted(self) -> bool:
        return self.status == "extracted"

    def value(self, name: str) -> str | None:
        f = self.fields.get(name)
        if f is None or f.value is None or not str(f.value).strip():
            return None
        return str(f.value).strip()


@dataclass
class InstitutionView:
    name: str
    address: str
    approved_intake: int
    faculty_count: int
    deficiency_status: str
    ter_payment_status: str


@dataclass
class ChecklistEntry:
    doc_type: str
    label: str
    requirement: str          # required | optional (after resolving conditionals)
    configured_as: str        # required | optional | conditional
    reason: str               # why this requirement applies
    condition_unresolved: bool = False


@dataclass
class VerificationView:
    """Latest issuer verification for one document (see services/verification)."""

    status: str
    source: str
    is_mock: bool
    reference: str
    mismatches: list[dict]
    error: str | None


@dataclass
class ValidationContext:
    institution: InstitutionView
    documents: dict[str, DocView]          # current document per doc_type
    checklist: list[ChecklistEntry]
    today: date
    doc_labels: dict[str, str] = field(default_factory=dict)
    verifications: dict[str, VerificationView] = field(default_factory=dict)  # by document id

    def label(self, doc_type: str) -> str:
        return self.doc_labels.get(doc_type, doc_type.replace("_", " "))


@dataclass
class FindingDraft:
    """What a check reports. The evaluator adds rule id, category, severity, etc."""

    title: str
    explanation: str
    document_id: str | None = None
    found_value: str | None = None
    expected_value: str | None = None
    evidence: dict | None = None


@dataclass
class CheckResult:
    findings: list[FindingDraft] = field(default_factory=list)
    incomplete: list[dict] = field(default_factory=list)   # [{document_id, reason}]
