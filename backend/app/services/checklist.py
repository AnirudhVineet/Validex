"""Resolve a YAML checklist for one application: required / optional / conditional -> state."""
import operator

from app.models import Application, Institution
from app.services.rules.context import ChecklistEntry
from app.services.rules.schema import ChecklistConfig, ChecklistItemConfig

_OPS = {"gt": operator.gt, "gte": operator.ge, "lt": operator.lt,
        "lte": operator.le, "eq": operator.eq, "ne": operator.ne}
_OP_TEXT = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "eq": "=", "ne": "!="}


def _computed_value(name: str, app: Application, inst: Institution) -> float | None:
    requested = (app.form_data or {}).get("requested_intake")
    if requested is None:
        return None
    if name == "requested_intake":
        return float(requested)
    if name == "intake_increase":
        return float(requested) - float(inst.approved_intake)
    return None


def _resolve_item(item: ChecklistItemConfig, app: Application, inst: Institution,
                  label: str) -> ChecklistEntry:
    if item.requirement != "conditional":
        return ChecklistEntry(item.doc_type, label, item.requirement, item.requirement,
                              reason=f"{item.requirement} for this category")
    cond = item.condition
    actual = _computed_value(cond.value_of, app, inst)
    rule_text = f"{cond.value_of.replace('_', ' ')} {_OP_TEXT[cond.op]} {cond.value:g}"
    if actual is None:
        # Conservative: if we cannot evaluate the condition, treat the document as required.
        return ChecklistEntry(item.doc_type, label, "required", "conditional",
                              reason=f"required if {rule_text}; value not provided yet, treated as required",
                              condition_unresolved=True)
    applies = _OPS[cond.op](actual, cond.value)
    return ChecklistEntry(item.doc_type, label, "required" if applies else "optional", "conditional",
                          reason=f"{rule_text} is {'true' if applies else 'false'} ({cond.value_of.replace('_', ' ')} = {actual:g})")


def resolve_checklist(config: ChecklistConfig, app: Application, inst: Institution,
                      doc_labels: dict[str, str]) -> list[ChecklistEntry]:
    """Return one entry per checklist item with its resolved requirement and the reason."""
    return [_resolve_item(item, app, inst, doc_labels.get(item.doc_type, item.doc_type))
            for item in config.items]
