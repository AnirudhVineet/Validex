"""Deterministic validation checks. No LLM, no network.

Each check takes (ctx, params) and returns a CheckResult. Register new checks in CHECKS
together with a Pydantic model for their params so the rule loader can validate config.
If a check cannot run for a document (e.g. extraction failed), it records an `incomplete`
entry instead of guessing.
"""
import re
from collections.abc import Callable, Iterator
from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, Field
from rapidfuzz import fuzz

from app.services.rules.context import CheckResult, DocView, FindingDraft, ValidationContext


class NoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: dict[str, list[str]]


class WithinDaysParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    within_days: int = Field(ge=1, le=3650)


class PatternsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patterns: dict[str, str]


class ThresholdParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    threshold: int = Field(ge=50, le=100)


class ToleranceParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tolerance_pct: float = Field(ge=0, le=100)


# ---------- helpers ----------

def _extracted_docs(ctx: ValidationContext, result: CheckResult,
                    doc_types: set[str] | None = None) -> Iterator[DocView]:
    """Yield documents whose extraction finished; record the others as incomplete."""
    for doc in ctx.documents.values():
        if doc_types is not None and doc.doc_type not in doc_types:
            continue
        if doc.extracted:
            yield doc
        else:
            reason = doc.extraction_error or f"document is '{doc.status}', fields not available"
            result.incomplete.append({"document_id": doc.id, "doc_type": doc.doc_type, "reason": reason})


def _parse_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _date_field(doc: DocView, name: str, result: CheckResult) -> date | None:
    """Parsed date, or None. An unreadable (non-ISO) value is recorded as incomplete."""
    raw = doc.value(name)
    if raw is None:
        return None
    parsed = _parse_iso(raw)
    if parsed is None:
        result.incomplete.append({"document_id": doc.id, "doc_type": doc.doc_type,
                                  "reason": f"could not read {name.replace('_', ' ')} '{raw}'"})
    return parsed


_STOPWORDS = {"the", "of", "and", "&"}


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation and filler words, collapse spaces."""
    text = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    return " ".join(w for w in text.split() if w not in _STOPWORDS)


# ---------- checks ----------

def required_document_present(ctx: ValidationContext, _: NoParams) -> CheckResult:
    result = CheckResult()
    for item in ctx.checklist:
        if item.requirement != "required" or item.doc_type in ctx.documents:
            continue
        result.findings.append(FindingDraft(
            title=f"Required document missing: {ctx.label(item.doc_type)}",
            explanation=f"The checklist marks this document as required ({item.reason}) "
                        "but no file has been uploaded for it.",
            found_value="not uploaded",
            expected_value="uploaded",
        ))
    return result


def required_fields_present(ctx: ValidationContext, params: FieldsParams) -> CheckResult:
    result = CheckResult()
    for doc in _extracted_docs(ctx, result, set(params.fields)):
        for name in params.fields[doc.doc_type]:
            if doc.value(name) is not None:
                continue
            nice = name.replace("_", " ")
            result.findings.append(FindingDraft(
                title=f"{ctx.label(doc.doc_type)}: {nice} not found",
                explanation=f"The {nice} could not be read from the document. It may be missing, "
                            "blank or illegible.",
                document_id=doc.id,
                found_value="blank / not found",
                expected_value=f"a readable {nice}",
            ))
    return result


def document_type_matches(ctx: ValidationContext, _: NoParams) -> CheckResult:
    result = CheckResult()
    for doc in _extracted_docs(ctx, result):
        if doc.classified_type and doc.classified_type != doc.doc_type:
            result.findings.append(FindingDraft(
                title=f"File in '{ctx.label(doc.doc_type)}' slot looks like a different document",
                explanation="Keyword classification of the document text suggests it is a "
                            f"{ctx.label(doc.classified_type)}.",
                document_id=doc.id,
                found_value=ctx.label(doc.classified_type),
                expected_value=ctx.label(doc.doc_type),
            ))
    return result


def document_not_expired(ctx: ValidationContext, _: NoParams) -> CheckResult:
    result = CheckResult()
    for doc in _extracted_docs(ctx, result):
        expiry = _date_field(doc, "expiry_date", result)
        if expiry is not None and expiry < ctx.today:
            result.findings.append(FindingDraft(
                title=f"{ctx.label(doc.doc_type)} has expired",
                explanation=f"The expiry date {expiry.isoformat()} is before the scrutiny date "
                            f"{ctx.today.isoformat()}.",
                document_id=doc.id,
                found_value=expiry.isoformat(),
                expected_value=f">= {ctx.today.isoformat()}",
                evidence=doc.fields["expiry_date"].evidence(),
            ))
    return result


def expiring_soon(ctx: ValidationContext, params: WithinDaysParams) -> CheckResult:
    result = CheckResult()
    limit = ctx.today + timedelta(days=params.within_days)
    for doc in _extracted_docs(ctx, result):
        expiry = _parse_iso(doc.value("expiry_date"))
        if expiry is not None and ctx.today <= expiry <= limit:
            days = (expiry - ctx.today).days
            result.findings.append(FindingDraft(
                title=f"{ctx.label(doc.doc_type)} expires in {days} days",
                explanation=f"The document is valid today but expires on {expiry.isoformat()}, "
                            f"within the {params.within_days}-day review window.",
                document_id=doc.id,
                found_value=expiry.isoformat(),
                expected_value=f"> {limit.isoformat()}",
                evidence=doc.fields["expiry_date"].evidence(),
            ))
    return result


def valid_dates(ctx: ValidationContext, _: NoParams) -> CheckResult:
    result = CheckResult()
    for doc in _extracted_docs(ctx, result):
        issue = _date_field(doc, "issue_date", result)
        expiry = _parse_iso(doc.value("expiry_date"))
        if issue is not None and issue > ctx.today:
            result.findings.append(FindingDraft(
                title=f"{ctx.label(doc.doc_type)}: issue date is in the future",
                explanation=f"Issue date {issue.isoformat()} is after the scrutiny date {ctx.today.isoformat()}.",
                document_id=doc.id, found_value=issue.isoformat(),
                expected_value=f"<= {ctx.today.isoformat()}",
                evidence=doc.fields["issue_date"].evidence(),
            ))
        if issue is not None and expiry is not None and issue >= expiry:
            result.findings.append(FindingDraft(
                title=f"{ctx.label(doc.doc_type)}: issue date is not before expiry date",
                explanation=f"Issue date {issue.isoformat()} should be earlier than expiry date {expiry.isoformat()}.",
                document_id=doc.id, found_value=f"issued {issue.isoformat()}, expires {expiry.isoformat()}",
                expected_value="issue date < expiry date",
                evidence=doc.fields["issue_date"].evidence(),
            ))
    return result


def identifier_format(ctx: ValidationContext, params: PatternsParams) -> CheckResult:
    result = CheckResult()
    for doc in _extracted_docs(ctx, result, set(params.patterns)):
        value = doc.value("certificate_number")
        pattern = params.patterns[doc.doc_type]
        if value is not None and not re.fullmatch(pattern, value):
            result.findings.append(FindingDraft(
                title=f"{ctx.label(doc.doc_type)}: certificate number format looks wrong",
                explanation=f"'{value}' does not match the expected pattern {pattern}.",
                document_id=doc.id, found_value=value, expected_value=f"pattern {pattern}",
                evidence=doc.fields["certificate_number"].evidence(),
            ))
    return result


def _similarity_check(ctx: ValidationContext, field: str, record_value: str, threshold: int,
                      scorer: Callable[[str, str], float], what: str) -> CheckResult:
    result = CheckResult()
    expected = normalize_text(record_value)
    for doc in _extracted_docs(ctx, result):
        value = doc.value(field)
        if value is None:
            continue
        score = round(scorer(normalize_text(value), expected))
        if score < threshold:
            result.findings.append(FindingDraft(
                title=f"{ctx.label(doc.doc_type)}: {what} differs from institute record",
                explanation=f"Fuzzy similarity {score}/100 is below the threshold {threshold}. "
                            "This may be a typo, a former name, or a document for another institution.",
                document_id=doc.id, found_value=value, expected_value=record_value,
                evidence=doc.fields[field].evidence(),
            ))
    return result


def name_matches_record(ctx: ValidationContext, params: ThresholdParams) -> CheckResult:
    return _similarity_check(ctx, "institution_name", ctx.institution.name, params.threshold,
                             fuzz.token_sort_ratio, "institution name")


def address_matches_record(ctx: ValidationContext, params: ThresholdParams) -> CheckResult:
    return _similarity_check(ctx, "address", ctx.institution.address, params.threshold,
                             fuzz.token_set_ratio, "address")


def faculty_count_matches_record(ctx: ValidationContext, params: ToleranceParams) -> CheckResult:
    result = CheckResult()
    for doc in _extracted_docs(ctx, result, {"faculty_list"}):
        raw = doc.value("faculty_count")
        record = ctx.institution.faculty_count
        if raw is None or not raw.isdigit() or record <= 0:
            continue
        count = int(raw)
        diff_pct = abs(count - record) / record * 100
        if diff_pct > params.tolerance_pct:
            result.findings.append(FindingDraft(
                title="Faculty list count differs from institute record",
                explanation=f"The list has {count} faculty rows; the record says {record} "
                            f"({diff_pct:.0f}% difference, tolerance {params.tolerance_pct:.0f}%).",
                document_id=doc.id, found_value=str(count), expected_value=str(record),
                evidence=doc.fields["faculty_count"].evidence(),
            ))
    return result


def ter_payment_paid(ctx: ValidationContext, _: NoParams) -> CheckResult:
    result = CheckResult()
    status = ctx.institution.ter_payment_status
    if status != "paid":
        result.findings.append(FindingDraft(
            title="TER payment not marked as paid on institute record",
            explanation=f"The institute record shows ter_payment_status = '{status}'.",
            found_value=status, expected_value="paid",
            evidence={"page": None, "bbox": None, "snippet": f"Institute record: ter_payment_status={status}"},
        ))
    return result


def no_open_deficiency(ctx: ValidationContext, _: NoParams) -> CheckResult:
    result = CheckResult()
    status = ctx.institution.deficiency_status
    if status not in ("none", "resolved"):
        result.findings.append(FindingDraft(
            title="Open deficiency on institute record",
            explanation=f"The institute record shows deficiency_status = '{status}'.",
            found_value=status, expected_value="none or resolved",
            evidence={"page": None, "bbox": None, "snippet": f"Institute record: deficiency_status={status}"},
        ))
    return result


def low_confidence_fields(ctx: ValidationContext, _: NoParams) -> CheckResult:
    result = CheckResult()
    for doc in _extracted_docs(ctx, result):
        for f in doc.fields.values():
            if f.needs_confirmation:
                result.findings.append(FindingDraft(
                    title=f"{ctx.label(doc.doc_type)}: confirm extracted {f.name.replace('_', ' ')}",
                    explanation=f"Extracted by {f.source} with confidence {f.confidence:.2f}; "
                                "a person should confirm it against the document.",
                    document_id=doc.id, found_value=f.value, expected_value="confirmed value",
                    evidence=f.evidence(),
                ))
    return result


# name -> (function, params model)
CHECKS: dict[str, tuple[Callable[..., CheckResult], type[BaseModel]]] = {
    "required_document_present": (required_document_present, NoParams),
    "required_fields_present": (required_fields_present, FieldsParams),
    "document_type_matches": (document_type_matches, NoParams),
    "document_not_expired": (document_not_expired, NoParams),
    "expiring_soon": (expiring_soon, WithinDaysParams),
    "valid_dates": (valid_dates, NoParams),
    "identifier_format": (identifier_format, PatternsParams),
    "name_matches_record": (name_matches_record, ThresholdParams),
    "address_matches_record": (address_matches_record, ThresholdParams),
    "faculty_count_matches_record": (faculty_count_matches_record, ToleranceParams),
    "ter_payment_paid": (ter_payment_paid, NoParams),
    "no_open_deficiency": (no_open_deficiency, NoParams),
    "low_confidence_fields": (low_confidence_fields, NoParams),
}
