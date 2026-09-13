"""Structural causal-container receipts, with no text, URLs or provider field values."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

BOUNDS = dict(direct_targets=4, new_containers=8, newly_visible=8, changed_selected=4,
              identity_candidates=64, opener_attributes=24)
BOUND_CODES = frozenset("DETAIL_BOUND_" + k.upper() for k in BOUNDS)
Category = Literal["direct_targets", "new_containers", "newly_visible", "changed_selected",
                   "identity_candidates", "opener_attributes"]
Reason = Literal["DIRECT_REFERENCE", "NEW_CONTAINER", "NEWLY_VISIBLE", "SELECTION_CHANGED"]
RELEVANCE = dict(DIRECT_REFERENCE=("A", 400), NEW_CONTAINER=("B", 300),
                 NEWLY_VISIBLE=("C", 200), SELECTION_CHANGED=("D", 100))


class Structural(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RankedContainer(Structural):
    level: Literal["A", "B", "C", "D"]
    score: Literal[400, 300, 200, 100]
    reasons: list[Reason] = Field(min_length=1, max_length=4)
    category: Literal["dialogs", "panels", "forms", "tabs", "other"]

    @model_validator(mode="after")
    def rank(self):
        if (self.level, self.score) != max((RELEVANCE[r] for r in self.reasons), key=lambda x: x[1]):
            raise ValueError("DETAIL_CONTAINER_UNVERIFIED")
        return self


class DetailContainerDiagnostic(Structural):
    version: Literal[1]
    stage: Literal["BEFORE_CLICK", "AFTER_CLICK", "DOM_DIFF", "IDENTITY", "FIELD_MAPPING"]
    click_dispatched: bool
    row_verified: bool
    opener_verified: bool
    baseline_container_count: int = Field(ge=0, le=1000000)
    ignored_unchanged_count: int = Field(ge=0, le=1000000)
    candidate_count: int = Field(ge=0, le=1000000)
    categories: dict[str, int]
    counts: dict[str, int]
    limits: dict[str, int]
    ranked_candidates: list[RankedContainer] = Field(max_length=24)
    selected_level: Literal["A", "B", "C", "D"] | None
    failed_category: Category | None
    measured: int | None = Field(ge=0, le=1000000)
    maximum: int | None = Field(ge=0, le=1000000)

    @model_validator(mode="after")
    def fixed_bounds_and_counts(self):
        if (self.limits != BOUNDS or set(self.counts) != set(BOUNDS)
            or set(self.categories) != {"dialogs", "panels", "forms", "tabs", "other"}
            or any(type(n) is not int or not 0 <= n <= 1000000 for n in [*self.counts.values(), *self.categories.values()])
            or sum(self.categories.values()) != self.candidate_count
            or self.stage == "BEFORE_CLICK" and self.click_dispatched):
            raise ValueError("DETAIL_CONTAINER_UNVERIFIED")
        if self.failed_category:
            if (self.maximum != BOUNDS[self.failed_category] or self.measured != self.counts[self.failed_category]
                or self.measured <= self.maximum):
                raise ValueError("DETAIL_CONTAINER_UNVERIFIED")
        elif self.measured is not None or self.maximum is not None:
            raise ValueError("DETAIL_CONTAINER_UNVERIFIED")
        if self.ranked_candidates:
            scores = [r.score for r in self.ranked_candidates]
            if len(scores) != self.candidate_count or scores != sorted(scores, reverse=True):
                raise ValueError("DETAIL_CONTAINER_UNVERIFIED")
            if self.selected_level is not None and (self.selected_level != self.ranked_candidates[0].level
                or len(scores) > 1 and scores[0] == scores[1]):
                raise ValueError("DETAIL_CONTAINER_UNVERIFIED")
        return self
