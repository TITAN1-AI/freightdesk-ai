"""Metadata-only candidate contracts. No activated locators, private values, or write authority."""

import hashlib
import json
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.core.config import ROOT
from executors.ascend_extension.controller import IdentityEvidence, Strict
from executors.ascend_extension.native import canonical
from executors.ascend_extension.view_contract import AscendLoadBoardViewContract

SCOPE = json.loads((ROOT / "extensions/ascend-x1/detail-scope.json").read_text(encoding="utf-8"))
Section = Literal["Identity", "Assignment", "Status", "Pickup", "Delivery"]
Level = Literal["LEVEL_1", "LEVEL_2", "LEVEL_3", "LEVEL_4", "LEVEL_5"]


class LocatorCandidate(Strict):
    section: Section
    label: str | None = Field(max_length=40)
    strategy: Literal["LABEL_CONTROL", "ARIA_LABEL", "ARIA_LABELLEDBY", "TABLE_HEADER", "NEIGHBOR", "PROVIDER_ATTRIBUTE"]
    tag: Literal["input", "select", "textarea", "output", "div", "span"]
    control_type: Literal["text", "tel", "date", "time", "datetime-local", "number", "email", "OTHER"]
    role: Literal["textbox", "combobox", "status"] | None
    attribute_names: list[Literal["id", "name", "role", "aria-selected", "aria-expanded", "aria-controls", "aria-label", "aria-labelledby", "data-load-id", "data-field", "data-target", "data-bs-target"]] = Field(max_length=12)
    relative_path: list[int] = Field(max_length=10)
    neighbor_labels: list[str] = Field(max_length=8)
    value_present: bool
    conflicting: bool


class FieldObservation(Strict):
    field: str
    evidence_level: Level | None
    confidence: Literal["VERIFIED", "PROPOSED", "UNKNOWN"]
    presence: Literal["PRESENT", "EMPTY", "UNKNOWN"]
    candidates: list[LocatorCandidate] = Field(max_length=8)

    @model_validator(mode="after")
    def fixed_scope_and_score(self):
        if self.field not in SCOPE:
            raise ValueError("DETAIL_CONTRACT_INVALID")
        definition = SCOPE[self.field]
        for c in self.candidates:
            if (c.section != definition["section"]
                or c.label is not None and c.label not in definition["labels"]
                or any(n not in definition["labels"] for n in c.neighbor_labels)
                or any(type(n) is not int or n < 0 or n > 10000 for n in c.relative_path)):
                raise ValueError("DETAIL_CONTRACT_INVALID")
            if c.strategy == "PROVIDER_ATTRIBUTE" and "data-field" not in c.attribute_names:
                raise ValueError("DETAIL_CONTRACT_INVALID")
            if c.strategy != "PROVIDER_ATTRIBUTE" and c.label is None:
                raise ValueError("DETAIL_CONTRACT_INVALID")
        confidence, level, presence = "UNKNOWN", None, "UNKNOWN"
        if self.field == "load_id":
            confidence, level, presence = "VERIFIED", "LEVEL_1", "PRESENT"
        elif len(self.candidates) == 1 and not self.candidates[0].conflicting:
            candidate = self.candidates[0]
            level = ("LEVEL_1" if candidate.strategy == "PROVIDER_ATTRIBUTE" else "LEVEL_2"
                     if candidate.strategy in {"LABEL_CONTROL", "ARIA_LABEL", "ARIA_LABELLEDBY"} else "LEVEL_3")
            confidence = "PROPOSED" if level == "LEVEL_3" else "VERIFIED"
            presence = "PRESENT" if candidate.value_present else "EMPTY"
        if (self.confidence, self.evidence_level, self.presence) != (confidence, level, presence):
            raise ValueError("DETAIL_CONTRACT_INVALID")
        return self


class AscendLoadDetailContract(Strict):
    schema_version: Literal[1]
    provider: Literal["AscendTMS"]
    view: Literal["LOAD_DETAIL"]
    source: Literal["live extension DOM"]
    validation_load_id: str = Field(pattern=r"^[0-9]{1,20}$")
    observed_at: float = Field(ge=0)
    identity: IdentityEvidence
    fields: list[FieldObservation] = Field(min_length=len(SCOPE), max_length=len(SCOPE))
    container_reasons: list[Literal["NEW_CONTAINER", "NEWLY_VISIBLE", "STRUCTURE_CHANGED", "DIRECT_REFERENCE", "SELECTION_CHANGED"]] = Field(min_length=1, max_length=4)
    contract_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    activation: Literal["CANDIDATE_ONLY"]
    writes_allowed: Literal[False]
    values_included: Literal[False]

    @field_validator("writes_allowed", "values_included", mode="before")
    @classmethod
    def exact_false(cls, value):
        if value is not False:
            raise ValueError("DETAIL_CONTRACT_INVALID")
        return value

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_schema(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("DETAIL_CONTRACT_INVALID")
        return value

    @model_validator(mode="after")
    def identity_and_fingerprint(self):
        i = self.identity
        if (i.expected_load_id != self.validation_load_id or i.observed_load_id != self.validation_load_id
            or not (i.detail_field_match if i.identity_strategy == "PROVIDER_DETAIL_FIELD" else
                    i.newly_visible and i.direct_panel_reference and
                    (i.opener_identity_match if i.identity_strategy == "PROVIDER_OPENER_IDENTITY" else i.selection_transition))):
            raise ValueError("DETAIL_IDENTITY_MISSING")
        i.view_contract.require_active()
        if [f.field for f in self.fields] != list(SCOPE):
            raise ValueError("DETAIL_CONTRACT_INVALID")
        structure = [{"field": f.field, "candidates": [c.model_dump(exclude={"value_present"}) for c in f.candidates]} for f in self.fields]
        if hashlib.sha256(canonical(structure)).hexdigest() != self.contract_fingerprint:
            raise ValueError("DETAIL_CONTRACT_INVALID")
        return self


class DetailDiscoveryEvidence(Strict):
    view_contract: AscendLoadBoardViewContract
    load_id: str = Field(pattern=r"^[0-9]{1,20}$")
    board_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    contract: AscendLoadDetailContract


def sanitized_summary(contract: AscendLoadDetailContract):
    """Terminal-safe projection: no DOM attribute values, selectors or provider field values."""
    return {f.field: {"presence": f.presence, "mapping": f.confidence, "evidence_level": f.evidence_level}
            for f in contract.fields}
