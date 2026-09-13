"""Sanitized provider view evidence. The host resolves it without route, row IDs or counts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

View = Literal["ACTIVE_LOADS", "ALL_LOADS", "READY_FOR_ACCOUNTING", "OTHER"]
StateClass = Literal["active", "selected", "is-active", "ui-tabs-active", "ui-state-active"]
LABELS = {
    "Active Loads": "ACTIVE_LOADS",
    "All Loads": "ALL_LOADS",
    "Ready for Accounting": "READY_FOR_ACCOUNTING",
    "OTHER": "OTHER",
}


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    kind: Literal["CONTROL", "TITLE", "CONTAINER"]
    label: Literal["Active Loads", "All Loads", "Ready for Accounting", "OTHER"]
    view: View
    visible: bool
    aria_selected: bool | None
    aria_pressed: bool | None
    aria_current: bool
    active: bool
    parent_active: bool
    safe_classes: list[StateClass] = Field(max_length=5)
    parent_safe_classes: list[StateClass] = Field(max_length=5)
    data_view: View | None
    conflicting_identity: bool
    visible_linked_panel: bool
    unique_linked_panel: bool

    @model_validator(mode="after")
    def consistent(self):
        if (
            LABELS[self.label] != self.view
            or self.active != bool(self.safe_classes)
            or self.parent_active != bool(self.parent_safe_classes)
        ):
            raise ValueError("RECEIPT_INVALID")
        if self.data_view not in {None, self.view} and not self.conflicting_identity:
            raise ValueError("RECEIPT_INVALID")
        return self

    def selected(self):
        return (
            self.aria_selected is True
            or self.aria_pressed is True
            or self.aria_current
            or self.active
            or self.parent_active
        )


class AscendLoadBoardViewContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    contract: Literal["AscendLoadBoardViewContract"]
    version: Literal[1]
    provider: Literal["AscendTMS"]
    source: Literal["provider DOM"]
    candidate_control_count: int = Field(ge=0, le=33)
    candidate_count: int = Field(ge=0, le=33)
    candidate_bound_exceeded: bool
    candidates: list[Candidate] = Field(max_length=33)
    view: Literal["ACTIVE_LOADS", "ALL_LOADS", "READY_FOR_ACCOUNTING", "OTHER", "UNKNOWN"]
    confidence: Literal["VERIFIED", "UNKNOWN"]
    reason: Literal[
        "NO_PROVIDER_SIGNAL",
        "CANDIDATE_BOUND",
        "CONFLICTING_PROVIDER_SIGNALS",
        "AMBIGUOUS_PROVIDER_SIGNALS",
        "PROVIDER_SIGNAL",
    ]

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("RECEIPT_INVALID")
        return value

    @model_validator(mode="after")
    def resolve(self):
        if (
            type(self.version) is not int
            or self.candidate_count != len(self.candidates)
            or self.candidate_control_count != sum(c.kind == "CONTROL" for c in self.candidates)
            or self.candidate_bound_exceeded != (self.candidate_count > 32)
        ):
            raise ValueError("RECEIPT_INVALID")
        shown = [c for c in self.candidates if c.visible]
        selected = [c for c in shown if c.kind == "CONTROL" and c.selected()]
        signals = [
            c
            for c in shown
            if c.kind != "CONTROL"
            or c.selected()
            or (
                c.unique_linked_panel
                and c.visible_linked_panel
                and c.aria_selected is not False
                and c.aria_pressed is not False
            )
        ]
        view, confidence, reason = "UNKNOWN", "UNKNOWN", "NO_PROVIDER_SIGNAL"
        if self.candidate_bound_exceeded:
            reason = "CANDIDATE_BOUND"
        elif any(
            c.conflicting_identity
            or (
                c.kind == "CONTROL" and c.selected() and (c.aria_selected is False or c.aria_pressed is False)
            )
            for c in shown
        ):
            reason = "CONFLICTING_PROVIDER_SIGNALS"
        elif len(selected) > 1 or len({c.view for c in signals}) > 1:
            reason = "AMBIGUOUS_PROVIDER_SIGNALS"
        elif signals:
            view, confidence, reason = signals[0].view, "VERIFIED", "PROVIDER_SIGNAL"
        if (self.view, self.confidence, self.reason) != (view, confidence, reason):
            raise ValueError("RECEIPT_INVALID")
        return self

    def require_active(self):
        if self.confidence != "VERIFIED":
            raise PermissionError("ACTIVE_VIEW_UNVERIFIED")
        if self.view != "ACTIVE_LOADS":
            raise PermissionError("ACTIVE_VIEW_NOT_ACTIVE_LOADS")
