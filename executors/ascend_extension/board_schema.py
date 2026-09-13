"""Sanitized structural diagnostics only; never accepts provider row values."""

from typing import Literal

from pydantic import Field, model_validator

from executors.ascend_extension.controller import Strict
from integrations.ascend.ops_board import HEADERS

REQUIRED = [h for h in HEADERS if h]
Predicate = Literal[
    "CANDIDATE_GRID_BOUND", "NO_VISIBLE_GRID", "REQUIRED_HEADERS_MISSING", "AMBIGUOUS_DATA_GRIDS",
    "HEADER_COUNT_MISMATCH", "DUPLICATE_REQUIRED_HEADERS", "HEADER_SPAN", "ROW_SPAN",
    "ARIA_COLUMN_ALIGNMENT", "ROW_COUNT_BOUND", "ROW_CELL_COUNT_MISMATCH", "EMPTY_STATE_UNVERIFIED",
    "INITIALIZATION_BUSY", "ROW_IDENTITY_INVALID", "DUPLICATE_LOAD_ID", "STABILITY_TIMEOUT",
    "HOST_DUPLICATE_LOAD_ID", "HOST_BOARD_HASH_MISMATCH", "STRUCTURAL_METADATA_UNAVAILABLE",
]


class GridStructure(Strict):
    candidate_index: int = Field(ge=0, le=29)
    visible: bool
    data_bearing: bool
    has_body: bool
    header_count: int = Field(ge=0, le=10000)
    header_labels: list[str] = Field(max_length=64)
    header_visible: list[bool] = Field(max_length=64)
    row_count: int = Field(ge=0, le=100000)
    row_visible_cell_counts: list[int] = Field(max_length=64)
    row_cell_counts: list[int] = Field(max_length=64)
    required_header_mapping: dict[str, int | None]
    missing_headers: list[str] = Field(max_length=len(REQUIRED))
    duplicate_headers: list[str] = Field(max_length=len(REQUIRED))
    header_spans: bool
    row_spans: bool
    aria_column_mismatch: bool
    initialization_busy: bool
    empty_marker: bool

    @model_validator(mode="after")
    def sanitized(self):
        if (set(self.required_header_mapping) != set(REQUIRED)
            or any(n not in REQUIRED + ["UNKNOWN_LABEL", "EMPTY_LABEL"] for n in self.header_labels)
            or any(n not in REQUIRED for n in self.missing_headers + self.duplicate_headers)
            or any(n < 0 or n > 10000 for n in self.row_cell_counts + self.row_visible_cell_counts)
            or any(n is not None and not 0 <= n < self.header_count for n in self.required_header_mapping.values())
            or len(self.header_labels) != min(self.header_count, 64)
            or len(self.header_visible) != len(self.header_labels)):
            raise ValueError("BOARD_SCHEMA_INVALID")
        # Fully represented headers must justify every exported semantic index and missing/duplicate claim.
        if self.header_count <= 64:
            for name in REQUIRED:
                positions = [i for i, label in enumerate(self.header_labels) if label == name]
                if (self.required_header_mapping[name] != (positions[0] if len(positions) == 1 else None)
                    or (name in self.missing_headers) != (len(positions) == 0)
                    or (name in self.duplicate_headers) != (len(positions) > 1)):
                    raise ValueError("BOARD_SCHEMA_INVALID")
        return self


class PaginationStructure(Strict):
    page_size: int | None = Field(default=None, ge=0, le=9999)
    next_disabled: bool | None = None
    previous_disabled: bool | None = None


class BoardSchemaDiagnostic(Strict):
    version: Literal[1]
    candidate_grid_count: int = Field(ge=0, le=10000)
    candidates: list[GridStructure] = Field(max_length=30)
    failed_predicate: Predicate | None
    selected_candidate: int | None = Field(default=None, ge=0, le=29)
    render_samples: int = Field(ge=1, le=100)
    pagination: PaginationStructure
    metadata_truncated: bool = False

    @model_validator(mode="after")
    def counts(self):
        indexes = [c.candidate_index for c in self.candidates]
        if (not self.metadata_truncated and indexes != list(range(min(self.candidate_grid_count, 30)))
            or indexes != sorted(set(indexes))
            or any(i >= min(self.candidate_grid_count, 30) for i in indexes)
            or self.selected_candidate is not None and self.selected_candidate not in indexes):
            raise ValueError("BOARD_SCHEMA_INVALID")
        return self
