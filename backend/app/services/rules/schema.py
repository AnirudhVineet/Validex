"""Pydantic models describing the rule and checklist YAML files.

Loading a YAML file goes through these models, so malformed config is rejected with a
clear error message before it can be used.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums import FindingCategory, Severity


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check: str = Field(min_length=1)
    params: dict = Field(default_factory=dict)


class RuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Z]{2,5}-[0-9]{3}$")
    description: str = Field(min_length=3)
    category: FindingCategory
    condition: Condition
    severity: Severity
    recommended_action: str = Field(min_length=3)
    version: int = Field(ge=1)
    visible_to_applicant: bool


class RuleSetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    illustrative: bool
    notice: str = ""
    name: str = Field(pattern=r"^[a-z0-9_]+$")
    version: int = Field(ge=1)
    rules: list[RuleConfig] = Field(min_length=1)

    @field_validator("rules")
    @classmethod
    def unique_ids(cls, rules: list[RuleConfig]) -> list[RuleConfig]:
        seen: set[str] = set()
        for rule in rules:
            if rule.id in seen:
                raise ValueError(f"duplicate rule id {rule.id}")
            seen.add(rule.id)
        return rules


class ChecklistCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value_of: Literal["intake_increase", "requested_intake"]
    op: Literal["gt", "gte", "lt", "lte", "eq", "ne"]
    value: float


class ChecklistItemConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_type: str
    requirement: Literal["required", "optional", "conditional"]
    description: str = ""
    condition: ChecklistCondition | None = None

    @model_validator(mode="after")
    def condition_only_when_conditional(self) -> "ChecklistItemConfig":
        if self.requirement == "conditional" and self.condition is None:
            raise ValueError(f"{self.doc_type}: conditional item needs a condition")
        if self.requirement != "conditional" and self.condition is not None:
            raise ValueError(f"{self.doc_type}: only conditional items may have a condition")
        return self


class FormFieldConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    type: Literal["integer", "text"]
    required: bool = False


class ChecklistConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    illustrative: bool
    notice: str = ""
    name: str = Field(pattern=r"^[a-z0-9_]+$")
    title: str
    version: int = Field(ge=1)
    form_fields: list[FormFieldConfig] = Field(default_factory=list)
    items: list[ChecklistItemConfig] = Field(min_length=1)
