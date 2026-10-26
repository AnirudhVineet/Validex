"""Unit tests for each deterministic check, using hand-built contexts (no DB, no files)."""
from datetime import date

from app.enums import FindingCategory, Severity
from app.services.rules import checks
from app.services.rules.context import ChecklistEntry, DocView, FieldView, InstitutionView, ValidationContext
from app.services.rules.evaluator import evaluate
from app.services.rules.schema import RuleSetConfig

TODAY = date(2026, 10, 26)
INST = InstitutionView(name="SYNTHETIC Institute of Technology, Demo Nagar",
                       address="Plot 12, Fictional Industrial Area, Demo Nagar, Sample State 000001",
                       approved_intake=300, faculty_count=24, deficiency_status="none", ter_payment_status="paid")


def field(name, value, conf=0.98, needs=False):
    return FieldView(name, value, conf, 1, [10, 10, 50, 20], "pdf_text", needs)


def doc(doc_type="fire_noc", status="extracted", classified=None, **values):
    return DocView(id=f"doc-{doc_type}", doc_type=doc_type, status=status,
                   classified_type=classified or doc_type, extraction_error=None,
                   fields={k: field(k, v) for k, v in values.items()})


def ctx(*docs, inst=INST, checklist=None):
    return ValidationContext(institution=inst, documents={d.doc_type: d for d in docs},
                             checklist=checklist or [], today=TODAY)


def test_required_document_missing():
    checklist = [ChecklistEntry("fire_noc", "Fire NOC", "required", "required", "required"),
                 ChecklistEntry("accreditation_certificate", "Acc", "optional", "optional", "optional")]
    result = checks.required_document_present(ctx(checklist=checklist), checks.NoParams())
    assert len(result.findings) == 1
    assert "fire noc" in result.findings[0].title


def test_required_fields_blank():
    d = doc(institution_name="X", certificate_number="  ")
    result = checks.required_fields_present(ctx(d), checks.FieldsParams(fields={"fire_noc": ["institution_name", "certificate_number", "expiry_date"]}))
    assert {f.title.split(": ")[1] for f in result.findings} == {"certificate number not found", "expiry date not found"}


def test_failed_extraction_is_incomplete_not_a_guess():
    d = DocView("d1", "fire_noc", "failed", None, "OCR not available", {})
    result = checks.document_not_expired(ctx(d), checks.NoParams())
    assert result.findings == []
    assert result.incomplete[0]["reason"] == "OCR not available"


def test_expired_and_expiring_soon():
    expired = checks.document_not_expired(ctx(doc(expiry_date="2026-10-25")), checks.NoParams())
    assert expired.findings[0].found_value == "2026-10-25"
    assert expired.findings[0].evidence["bbox"] == [10, 10, 50, 20]
    assert checks.document_not_expired(ctx(doc(expiry_date="2026-10-26")), checks.NoParams()).findings == []
    soon = checks.expiring_soon(ctx(doc(expiry_date="2026-12-01")), checks.WithinDaysParams(within_days=90))
    assert len(soon.findings) == 1
    later = checks.expiring_soon(ctx(doc(expiry_date="2027-06-01")), checks.WithinDaysParams(within_days=90))
    assert later.findings == []


def test_unreadable_date_is_incomplete():
    result = checks.document_not_expired(ctx(doc(expiry_date="3l-O3-2O25")), checks.NoParams())
    assert result.findings == [] and "could not read" in result.incomplete[0]["reason"]


def test_invalid_dates():
    future = checks.valid_dates(ctx(doc(issue_date="2027-01-01", expiry_date="2030-01-01")), checks.NoParams())
    assert "future" in future.findings[0].title
    reversed_ = checks.valid_dates(ctx(doc(issue_date="2026-01-01", expiry_date="2025-01-01")), checks.NoParams())
    assert "not before expiry" in reversed_.findings[0].title


def test_identifier_format():
    params = checks.PatternsParams(patterns={"fire_noc": "^FNOC-[0-9]{4}-[0-9]{6}$"})
    assert checks.identifier_format(ctx(doc(certificate_number="FNOC-2026-123456")), params).findings == []
    assert len(checks.identifier_format(ctx(doc(certificate_number="FNOC/2026/123456")), params).findings) == 1


def test_name_and_address_matching_is_tolerant_but_catches_other_institutions():
    params = checks.ThresholdParams(threshold=88)
    ok = doc(institution_name="Synthetic Institute of Technology Demo Nagar")
    assert checks.name_matches_record(ctx(ok), params).findings == []
    bad = doc(institution_name="SYNTHETIC Riverside College of Arts, Elsewhere Town")
    finding = checks.name_matches_record(ctx(bad), params).findings[0]
    assert finding.expected_value == INST.name and "similarity" in finding.explanation
    addr = doc(address="Plot 12, Fictional Industrial Area, Demo Nagar")
    assert checks.address_matches_record(ctx(addr), checks.ThresholdParams(threshold=80)).findings == []


def test_faculty_count_tolerance():
    params = checks.ToleranceParams(tolerance_pct=10)
    assert checks.faculty_count_matches_record(ctx(doc("faculty_list", faculty_count="23")), params).findings == []
    assert len(checks.faculty_count_matches_record(ctx(doc("faculty_list", faculty_count="15")), params).findings) == 1


def test_institute_record_checks():
    unpaid = InstitutionView(**{**INST.__dict__, "ter_payment_status": "pending"})
    assert checks.ter_payment_paid(ctx(inst=unpaid), checks.NoParams()).findings[0].found_value == "pending"
    assert checks.ter_payment_paid(ctx(), checks.NoParams()).findings == []
    deficient = InstitutionView(**{**INST.__dict__, "deficiency_status": "open"})
    assert len(checks.no_open_deficiency(ctx(inst=deficient), checks.NoParams()).findings) == 1


def test_document_type_mismatch_and_low_confidence():
    wrong = doc("fire_noc", classified="affidavit", institution_name="x")
    assert len(checks.document_type_matches(ctx(wrong), checks.NoParams()).findings) == 1
    d = doc(institution_name="x")
    d.fields["institution_name"].needs_confirmation = True
    assert len(checks.low_confidence_fields(ctx(d), checks.NoParams()).findings) == 1


def test_evaluator_forces_anomaly_hidden_and_records_crashes(monkeypatch):
    config = RuleSetConfig.model_validate({
        "illustrative": True, "name": "t", "version": 1, "rules": [
            {"id": "ANO-001", "description": "test", "category": "anomaly", "severity": "medium",
             "condition": {"check": "ter_payment_paid"}, "recommended_action": "review",
             "version": 1, "visible_to_applicant": True},
            {"id": "BRK-001", "description": "crashes", "category": "expiry", "severity": "low",
             "condition": {"check": "no_open_deficiency"}, "recommended_action": "fix it",
             "version": 1, "visible_to_applicant": True},
        ]})
    unpaid = InstitutionView(**{**INST.__dict__, "ter_payment_status": "pending"})

    def boom(*_):
        raise RuntimeError("bug")

    monkeypatch.setitem(checks.CHECKS, "no_open_deficiency", (boom, checks.NoParams))
    result = evaluate(ctx(inst=unpaid), config)
    assert result.findings[0].rule.category == FindingCategory.anomaly
    assert result.findings[0].visible_to_applicant is False
    assert result.incomplete[0]["rule_id"] == "BRK-001"
    assert result.findings[0].rule.severity == Severity.medium
