"""Run a validated rule set against a ValidationContext. Pure function, no DB access."""
from dataclasses import dataclass, field

from app.enums import FindingCategory
from app.services.rules.checks import CHECKS
from app.services.rules.context import FindingDraft, ValidationContext
from app.services.rules.schema import RuleConfig, RuleSetConfig


@dataclass
class RuleFinding:
    rule: RuleConfig
    draft: FindingDraft

    @property
    def visible_to_applicant(self) -> bool:
        # Anomaly indicators are never shown to applicants, whatever the rule config says.
        if self.rule.category == FindingCategory.anomaly:
            return False
        return self.rule.visible_to_applicant


@dataclass
class EvaluationResult:
    findings: list[RuleFinding] = field(default_factory=list)
    incomplete: list[dict] = field(default_factory=list)  # [{rule_id, document_id, doc_type, reason}]


def evaluate(ctx: ValidationContext, rule_set: RuleSetConfig) -> EvaluationResult:
    """Run every rule. A crashing check is recorded as incomplete, never silently skipped."""
    out = EvaluationResult()
    for rule in rule_set.rules:
        func, params_model = CHECKS[rule.condition.check]
        params = params_model.model_validate(rule.condition.params)
        try:
            result = func(ctx, params)
        except Exception as exc:  # noqa: BLE001 - a buggy check must not hide other results
            out.incomplete.append({"rule_id": rule.id, "document_id": None, "doc_type": None,
                                   "reason": f"check error: {type(exc).__name__}: {exc}"})
            continue
        out.findings += [RuleFinding(rule, d) for d in result.findings]
        out.incomplete += [{"rule_id": rule.id, **item} for item in result.incomplete]
    return out
