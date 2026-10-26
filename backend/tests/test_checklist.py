from app.enums import ApplicationCategory
from app.models import Application, Institution
from app.services.checklist import resolve_checklist
from app.services.rules.loader import CHECKLISTS_DIR, parse_checklist


def _resolve(form_data, category="eoa_increase_intake"):
    config = parse_checklist((CHECKLISTS_DIR / f"{category}.yaml").read_text(encoding="utf-8"))
    app = Application(category=ApplicationCategory(category), form_data=form_data)
    inst = Institution(name="x", aicte_ref="x", approved_intake=120)
    return {e.doc_type: e for e in resolve_checklist(config, app, inst, {})}


def test_conditional_required_when_increase_large():
    entry = _resolve({"requested_intake": 240})["accreditation_certificate"]
    assert entry.requirement == "required" and entry.configured_as == "conditional"
    assert "120" in entry.reason


def test_conditional_optional_when_increase_small():
    assert _resolve({"requested_intake": 150})["accreditation_certificate"].requirement == "optional"


def test_unresolved_condition_is_treated_as_required():
    entry = _resolve({})["accreditation_certificate"]
    assert entry.requirement == "required" and entry.condition_unresolved


def test_no_change_category_has_optional_accreditation():
    items = _resolve({}, "eoa_no_change")
    assert items["accreditation_certificate"].requirement == "optional"
    assert items["fire_noc"].requirement == "required"
