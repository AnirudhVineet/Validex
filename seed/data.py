"""SYNTHETIC institutions and demo scenarios. All names, places and IDs are fictional."""
import random

DEMO_INSTITUTION = {
    "name": "SYNTHETIC Institute of Technology, Demo Nagar",
    "address": "Plot 12, Fictional Industrial Area, Demo Nagar, Sample State 000001",
    "state": "Sample State",
    "aicte_ref": "SYN-1-0000000001",
    "prior_eoa_year": 2025,
    "approved_intake": 300,
    "faculty_count": 24,
    "deficiency_status": "none",
    "ter_payment_status": "paid",
    "is_synthetic": True,
}

_PLACES = ["Testpur", "Sampleville", "Mockabad", "Fictiongarh", "Placeholder Puram", "Example Kottai",
           "Dummy Ganj", "Prototype Pet", "Synthpur", "Stubwadi", "Fixture Halli", "Seedpur", "Mockingnagar",
           "Draftabad", "Specimen Kunj", "Templategarh", "Pilotpur", "Trialwadi", "Benchpur", "Modelganj",
           "Sandbox Nagar", "Staging Pet", "Previewpur", "Betaville"]
_KINDS = ["Institute of Technology", "College of Engineering", "School of Management",
          "Polytechnic", "Institute of Engineering and Technology", "College of Pharmacy"]
_ROADS = ["Mock Road", "Sample Main Road", "Test Avenue", "Fiction Lane", "Demo Ring Road"]
_STATES = ["Sample State", "Demo Pradesh", "Mock Rashtra", "Test Desh"]


def build_institutions(count: int = 25, seed: int = 42) -> list[dict]:
    """DEMO_INSTITUTION first, then count-1 deterministic synthetic institutions."""
    rng = random.Random(seed)
    out = [dict(DEMO_INSTITUTION)]
    for n in range(2, count + 1):
        place = _PLACES[n - 2]
        state = rng.choice(_STATES)
        out.append({
            "name": f"SYNTHETIC {rng.choice(_KINDS)}, {place}",
            "address": f"Plot {rng.randint(1, 99)}, {rng.choice(_ROADS)}, {place}, {state} {n:06d}",
            "state": state,
            "aicte_ref": f"SYN-1-{n:010d}",
            "prior_eoa_year": rng.choice([2024, 2025]),
            "approved_intake": rng.choice([60, 120, 180, 240, 300]),
            "faculty_count": rng.randint(12, 40),
            "deficiency_status": "none",
            "ter_payment_status": "paid",
            "is_synthetic": True,
        })
    # A few institutions with record-level issues (for REC-001 / REC-002 demos).
    out[5]["ter_payment_status"] = "pending"
    out[12]["ter_payment_status"] = "pending"
    out[8]["deficiency_status"] = "open"
    return out


# Each scenario becomes one seeded application. `docs` maps doc_type -> variant; omitted
# doc types are not uploaded. `target` is the status the seed drives the application to.
VALID_SET = {"fire_noc": "valid", "affidavit": "valid", "land_document": "valid", "faculty_list": "valid"}

SCENARIOS = [
    {"key": "clean", "institution": 1, "category": "eoa_no_change", "docs": VALID_SET,
     "target": "submitted", "expected": []},
    {"key": "expired_fire_noc", "institution": 2, "category": "eoa_no_change",
     "docs": {**VALID_SET, "fire_noc": "expired"}, "target": "under_scrutiny", "expected": ["EXP-001"]},
    {"key": "missing_affidavit", "institution": 3, "category": "eoa_no_change",
     "docs": {k: v for k, v in VALID_SET.items() if k != "affidavit"}, "target": "submitted",
     "expected": ["COMP-001"]},
    {"key": "land_name_mismatch", "institution": 4, "category": "eoa_no_change",
     "docs": {**VALID_SET, "land_document": "name_mismatch"}, "target": "under_scrutiny",
     "expected": ["CONS-001"]},
    {"key": "ter_pending", "institution": 5, "category": "eoa_no_change", "docs": VALID_SET,
     "target": "submitted", "expected": ["REC-001"]},
    {"key": "scanned_fire_noc", "institution": 6, "category": "eoa_no_change",
     "docs": {**VALID_SET, "fire_noc": "scanned"}, "target": "submitted", "expected": [],
     "note": "Needs Tesseract; without it the NOC checks are reported as incomplete."},
    {"key": "intake_increase_no_accreditation", "institution": 7, "category": "eoa_increase_intake",
     "form_data_increase": 120, "docs": VALID_SET, "target": "submitted", "expected": ["COMP-001"]},
    {"key": "open_deficiency_faculty_gap", "institution": 8, "category": "eoa_no_change",
     "docs": {**VALID_SET, "accreditation_certificate": "near_expiry"}, "faculty_ratio": 0.6,
     "target": "under_scrutiny", "expected": ["EXP-002", "CONS-003", "REC-002"]},
    {"key": "bad_certificate_format", "institution": 9, "category": "eoa_no_change",
     "docs": {**VALID_SET, "fire_noc": "bad_format"}, "target": "escalated", "expected": ["FMT-001"]},
    {"key": "returned_expired", "institution": 10, "category": "eoa_no_change",
     "docs": {**VALID_SET, "fire_noc": "expired"}, "target": "returned_for_correction", "expected": ["EXP-001"]},
    {"key": "complete_clean", "institution": 11, "category": "eoa_no_change", "docs": VALID_SET,
     "target": "scrutiny_complete", "expected": []},
    {"key": "draft_missing_field", "institution": 12, "category": "eoa_no_change",
     "docs": {**VALID_SET, "affidavit": "missing_field"}, "target": "draft", "expected": ["COMP-002", "REC-001"]},
]

# Files for the live demo upload (for the demo applicant's institution).
DEMO_UPLOADS = [
    ("fire_noc", "valid"), ("fire_noc", "expired"), ("fire_noc", "scanned"),
    ("affidavit", "valid"), ("land_document", "valid"), ("land_document", "name_mismatch"),
    ("faculty_list", "valid"), ("accreditation_certificate", "valid"),
]
