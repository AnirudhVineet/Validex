import pytest

from app.enums import RuleSetKind
from app.models import RuleSetVersion
from app.services.rules.loader import (
    CHECKLISTS_DIR, RULES_DIR, RuleSetError, get_checklist, get_rule_set, parse_checklist, parse_rule_set,
)

GOOD_RULE = """
illustrative: true
name: test
version: 1
rules:
  - id: TST-001
    description: test rule
    category: expiry
    severity: high
    condition: {check: document_not_expired}
    recommended_action: renew it
    version: 1
    visible_to_applicant: true
"""


def test_shipped_rule_set_and_checklists_are_valid():
    config = parse_rule_set((RULES_DIR / "core.yaml").read_text(encoding="utf-8"))
    assert config.illustrative is True
    assert len(config.rules) >= 10
    for path in CHECKLISTS_DIR.glob("*.yaml"):
        assert parse_checklist(path.read_text(encoding="utf-8")).illustrative is True


def test_good_rule_parses():
    assert parse_rule_set(GOOD_RULE).rules[0].id == "TST-001"


@pytest.mark.parametrize("broken, message", [
    (GOOD_RULE.replace("document_not_expired", "no_such_check"), "unknown check"),
    (GOOD_RULE.replace("severity: high", "severity: urgent"), "severity"),
    (GOOD_RULE.replace("illustrative: true", "illustrative: false"), "illustrative"),
    (GOOD_RULE.replace("id: TST-001", "id: bad id"), "id"),
    (GOOD_RULE.replace("    version: 1\n    visible", "    visible"), "version"),
    (GOOD_RULE.replace("{check: document_not_expired}",
                       "{check: expiring_soon, params: {within_days: -5}}"), "within_days"),
    (GOOD_RULE.replace("{check: document_not_expired}",
                       "{check: document_not_expired, params: {surprise: 1}}"), "surprise"),
    (GOOD_RULE + GOOD_RULE.split("rules:\n")[1], "duplicate rule id"),
    ("rules: [unclosed", "YAML syntax error"),
])
def test_malformed_rules_are_rejected_with_clear_error(broken, message):
    with pytest.raises(RuleSetError) as exc:
        parse_rule_set(broken)
    assert message in str(exc.value)


def test_conditional_checklist_item_needs_condition():
    text = """
illustrative: true
name: x
title: X
version: 1
items:
  - doc_type: fire_noc
    requirement: conditional
"""
    with pytest.raises(RuleSetError, match="needs a condition"):
        parse_checklist(text)


def test_rule_set_seeded_into_db_once(db):
    row, config = get_rule_set(db)
    again, _ = get_rule_set(db)
    assert row.id == again.id
    assert row.version == config.version
    assert db.query(RuleSetVersion).filter_by(kind=RuleSetKind.rules).count() == 1


def test_unknown_checklist_category(db):
    with pytest.raises(RuleSetError, match="no checklist"):
        get_checklist(db, "nonexistent")
