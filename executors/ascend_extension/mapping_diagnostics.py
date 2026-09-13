"""Fixed metadata-only capture receipts; never provider values."""
import json
from typing import Literal
from pydantic import Field, field_validator
from executors.ascend_extension.controller import Strict
from executors.ascend_extension.workspace_contracts import SCOPE

STAGES = ("TAB_VERIFIED", "SESSION_VERIFIED", "ENTITY_DISCOVERY", "LOAD_WORKSPACE_CANDIDATE_FOUND", "WORKSPACE_IDENTITY_VERIFIED", "SECTION_IDENTIFIED", "STRUCTURE_CAPTURED", "MAP_PERSISTED")


def _section_label(value):
    if value not in (*SCOPE["sections"], "UNCLASSIFIED"):
        raise ValueError("MAPPING_CONTRACT_INVALID")
    return value


StructureTag = Literal["a", "button", "div", "span", "li", "ul", "ol", "nav", "main", "section", "form", "h1", "h2", "h3", "legend", "table", "tbody", "tr", "td", "OTHER"]
StructureRole = Literal["tab", "button", "link", "tablist", "tabpanel", "region", "main", "navigation", "heading", "dialog", "OTHER"]
StateMarker = Literal["ARIA_SELECTED_TRUE", "ARIA_CURRENT_PAGE", "ARIA_CURRENT_TRUE", "CLASS_ACTIVE", "PARENT_CLASS_ACTIVE"]


class SectionReferenceShape(Strict):
    attribute: Literal["ARIA_CONTROLS", "HREF", "DATA_TARGET", "DATA_BS_TARGET"]
    shape: Literal["EMPTY", "SINGLE_ID", "ID_LIST", "FRAGMENT", "EMPTY_FRAGMENT", "SCRIPT_REFERENCE", "RELATIVE_PATH", "SAME_ORIGIN_URL", "OTHER"]


class SectionAnchorDestination(Strict):
    same_origin: bool
    same_path: bool
    fragment_present: bool
    query_present: bool


class SelectedSectionStructure(Strict):
    candidate_index: int = Field(ge=0, le=23)
    section_label: str
    tag: StructureTag
    role: StructureRole
    state_markers: list[StateMarker] = Field(max_length=5)
    references: list[SectionReferenceShape] = Field(max_length=4)
    id_present: bool
    aria_labelledby_present: bool
    onclick_present: bool
    parent_tag: StructureTag
    parent_role: StructureRole
    workspace_child_index: int | None = Field(default=None, ge=0, le=1000000)
    anchor_destination: SectionAnchorDestination | None = None

    _label = field_validator("section_label")(_section_label)


class HeadingSectionStructure(Strict):
    candidate_index: int = Field(ge=0, le=47)
    section_label: str
    tag: StructureTag
    root_kind: Literal["SECTION", "FORM", "TABPANEL", "REGION", "DATA_SECTION", "NONE"]
    predicate: Literal["ACCEPTED", "NOT_RECOGNIZED_LABEL", "NO_SUPPORTED_ROOT", "ROOT_IS_WORKSPACE", "ROOT_OUTSIDE_WORKSPACE", "ROOT_CONTAINS_TABLIST"]

    _label = field_validator("section_label")(_section_label)


class WorkspaceChildStructure(Strict):
    child_index: int = Field(ge=0, le=23)
    tag: StructureTag
    role: StructureRole
    visible: bool
    child_element_count: int = Field(ge=0, le=1000000)
    known_navigation_control_count: int = Field(ge=0, le=64)
    selected_control_count: int = Field(ge=0, le=1000000)
    descendant_field_control_count: int = Field(ge=0, le=1000000)
    immediate_heading_labels: list[str] = Field(max_length=48)

    @field_validator("immediate_heading_labels")
    @classmethod
    def fixed_labels(cls, values):
        for value in values:
            _section_label(value)
        return values


class SectionDiagnosticBound(Strict):
    category: Literal["SELECTED_CONTROLS", "HEADING_CANDIDATES", "WORKSPACE_DIRECT_CHILDREN"]
    measured: int = Field(ge=0, le=1000000)
    maximum: Literal[24, 48]


class SectionStructureDiagnostic(Strict):
    schema_version: Literal[1] = 1
    observation_scope: Literal["VERIFIED_WORKSPACE_ONLY"] = "VERIFIED_WORKSPACE_ONLY"
    status: Literal["CAPTURED", "PARTIAL", "UNAVAILABLE"]
    selected_controls: list[SelectedSectionStructure] = Field(max_length=24)
    heading_candidate_count: int | None = Field(ge=0, le=1000000)
    heading_candidates: list[HeadingSectionStructure] = Field(max_length=48)
    workspace_direct_child_count: int | None = Field(ge=0, le=1000000)
    workspace_direct_children: list[WorkspaceChildStructure] = Field(max_length=24)
    diagnostic_bounds: list[SectionDiagnosticBound] = Field(max_length=3)


class RouteHeadingRootDiagnostic(Strict):
    ancestor_depth: int = Field(ge=1, le=8)
    tag: StructureTag
    form_candidate_count: int | None = Field(default=None, ge=0, le=1000000)
    visible_form_count: int | None = Field(default=None, ge=0, le=16)
    field_candidate_count: int | None = Field(default=None, ge=0, le=1000000)
    forms_with_visible_fields: int | None = Field(default=None, ge=0, le=16)
    predicate: Literal["ELIGIBLE", "NOT_DIV", "NOT_VISIBLE", "CONTAINS_WORKSPACE_IDENTITY", "CONTAINS_SECTION_NAVIGATION", "CONTAINS_OTHER_SECTION_HEADING", "NO_VISIBLE_FORM_FIELDS", "FORM_CANDIDATE_BOUND", "FORM_FIELD_CANDIDATE_BOUND"]


SiblingPredicate = Literal["ELIGIBLE", "NOT_DIV", "NOT_VISIBLE", "CONTEXT_CONTAINS_IDENTITY", "CONTEXT_CONTAINS_OTHER_HEADING", "DIRECT_CHILD_BOUND", "CONTEXT_FORM_BOUND", "NO_VISIBLE_CONTEXT_FORMS", "HEADING_CHILD_NOT_UNIQUE", "FORM_CHILD_NOT_UNIQUE", "FORM_REGION_PRECEDES_HEADING", "FORM_REGION_NOT_DIV", "FORM_REGION_NOT_ALL_FORMS", "FORM_REGION_CONTAINS_IDENTITY", "FORM_REGION_CONTAINS_NAVIGATION", "FORM_REGION_CONTAINS_OTHER_HEADING", "FORM_FIELD_BOUND", "NO_VISIBLE_FORM_FIELDS", "CONTEXT_ANCESTOR_BOUND", "NO_ELIGIBLE_CONTEXT"]


class SiblingFormContextDiagnostic(Strict):
    ancestor_depth: int = Field(ge=1, le=8)
    direct_child_count: int = Field(ge=0, le=1000000)
    form_candidate_count: int | None = Field(default=None, ge=0, le=1000000)
    visible_form_count: int | None = Field(default=None, ge=0, le=16)
    field_candidate_count: int | None = Field(default=None, ge=0, le=1000000)
    heading_child_count: int | None = Field(default=None, ge=0, le=24)
    form_bearing_child_count: int | None = Field(default=None, ge=0, le=24)
    heading_child_index: int | None = Field(default=None, ge=0, le=23)
    form_child_index: int | None = Field(default=None, ge=0, le=23)
    all_visible_forms_contained: bool | None = None
    predicate: SiblingPredicate


class SiblingFormDiagnostic(Strict):
    strategy: Literal["NEAREST_HEADING_CONTEXT_UNIQUE_LATER_FORM_REGION"]
    context_count: int = Field(ge=0, le=8)
    selected_context_depth: int | None = Field(default=None, ge=1, le=8)
    context_candidates: list[SiblingFormContextDiagnostic] = Field(max_length=8)
    failed_predicate: SiblingPredicate | None = None


class RouteHeadingSectionDiagnostic(Strict):
    strategy: Literal["SELECTED_CURRENT_ROUTE_AND_MATCHING_HEADING"]
    route_anchor_candidate_count: int = Field(ge=0, le=24)
    matching_heading_count: int = Field(ge=0, le=48)
    ancestor_count: int = Field(ge=0, le=8)
    eligible_root_count: int = Field(ge=0, le=8)
    selected_ancestor_depth: int | None = Field(default=None, ge=1, le=8)
    visible_field_candidate_count: int | None = Field(default=None, ge=0, le=1000000)
    root_relationship: Literal["ANCESTOR_FORM_REGION", "SIBLING_FORM_REGION"] | None = None
    sibling_form_diagnostic: SiblingFormDiagnostic | None = None
    ancestor_candidates: list[RouteHeadingRootDiagnostic] = Field(max_length=8)
    failed_predicate: Literal["ROUTE_ANCHOR_COUNT_ZERO", "ROUTE_ANCHOR_COUNT_MULTIPLE", "MATCHING_HEADING_COUNT_ZERO", "MATCHING_HEADING_COUNT_MULTIPLE", "ANCESTOR_BOUND", "NO_ELIGIBLE_ROOT"] | None = None


class V2StructuralDiagnostic(Strict):
    schema_version: Literal[2]
    stage: Literal["PREFLIGHT", "BOUNDARY_VERIFIED", "GRAPH_CAPTURED", "RELATIONSHIPS_RESOLVED", "SECTION_VERIFIED"]
    predicate: Literal["V2_AUTHORITY_UNAVAILABLE", "V2_BINDING_CHANGED", "V2_BINDING_INVALID", "V2_BOUND_EXCEEDED", "V2_CAPTURE_FAILED", "V2_CLOSED", "V2_CONFIGURATION_INVALID", "V2_DOCUMENT_CHANGED", "V2_IDENTITY_CHANGED", "V2_IDENTITY_UNVERIFIED", "V2_JOB_ACTIVE", "V2_OBSERVATION_INVALID", "V2_ORIGIN_MISMATCH", "V2_PROTOCOL_MISMATCH", "V2_SCOPE_INVALID", "V2_SESSION_UNVERIFIED", "V2_STRUCTURE_CHANGED", "WAITING_FOR_OWNER_WORKSPACE", "SELECTED_CONTROL_NOT_UNIQUE", "TARGET_AND_HEADING_NOT_UNIQUE", "TARGET_CONTAINS_NAVIGATION", "TARGET_REFERENCE_UNRESOLVED", "COMPATIBILITY_ROOT_MISMATCH", "FIELD_GRAPH_MISMATCH"]
    bound_category: Literal["visited", "emitted", "depth", "attributes", "attributeBytes", "relations", "references", "labelNodes", "labelDepth", "geometry", "frontier", "labelBytes", "payloadBytes", "elapsedMs", "batch"] | None = None
    measured: int | None = Field(default=None, ge=0, le=10000000)
    maximum: int | None = Field(default=None, ge=0, le=10000000)


class MappingSectionDiagnostic(Strict):
    """Only bounded counts and fixed vocabulary from the section proof gate."""

    schema_version: Literal[1] = 1
    selected_candidate_count: int = Field(ge=0, le=1000000)
    recognized_section_labels: list[str] = Field(max_length=14)
    approved_state_markers: list[Literal["ARIA_SELECTED_TRUE", "ARIA_CURRENT_PAGE", "ARIA_CURRENT_TRUE", "CLASS_ACTIVE", "PARENT_CLASS_ACTIVE"]] = Field(max_length=5)
    target_relationship_kinds: list[Literal["ARIA_CONTROLS", "FRAGMENT", "DATA_TARGET", "DATA_BS_TARGET", "LABELLEDBY"]] = Field(max_length=5)
    visible_target_count: int = Field(ge=0, le=1000000)
    heading_root_count: int = Field(ge=0, le=48)
    unique_candidate_count: int = Field(ge=0, le=10000)
    failed_predicate: Literal["SELECTED_CANDIDATE_BOUND", "VISIBLE_TARGET_BOUND", "HEADING_CANDIDATE_BOUND", "UNIQUE_CANDIDATE_COUNT_ZERO", "UNIQUE_CANDIDATE_COUNT_MULTIPLE", "SECTION_CONTAINS_WORKSPACE_IDENTITY"] | None = None
    structure_diagnostic: SectionStructureDiagnostic | None = None
    route_heading_diagnostic: RouteHeadingSectionDiagnostic | None = None
    v2_diagnostic: V2StructuralDiagnostic | None = None

    @field_validator("recognized_section_labels")
    @classmethod
    def fixed_labels(cls, values):
        if any(value not in (*SCOPE["sections"], "UNCLASSIFIED") for value in values) or len(values) != len(set(values)):
            raise ValueError("MAPPING_CONTRACT_INVALID")
        return values

    @field_validator("approved_state_markers", "target_relationship_kinds")
    @classmethod
    def unique_markers(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("MAPPING_CONTRACT_INVALID")
        return values


class MappingDiagnostic(Strict):
    stage: Literal["TAB_VERIFIED", "SESSION_VERIFIED", "ENTITY_DISCOVERY", "LOAD_WORKSPACE_CANDIDATE_FOUND", "WORKSPACE_IDENTITY_VERIFIED", "SECTION_IDENTIFIED", "STRUCTURE_CAPTURED", "MAP_PERSISTED"]
    candidate_workspace_count: int = Field(ge=0, le=10000)
    identity_signal_count: int = Field(ge=0, le=10000)
    section_control_count: int = Field(ge=0, le=10000)
    elapsed_ms: int = Field(ge=0, le=3600000)
    section_diagnostic: MappingSectionDiagnostic | None = None


def record_diagnostic(db, state, lease, pending, now, code=None):
    diagnostic = state.get("mapping_diagnostic")
    if diagnostic is None:
        return
    safe = MappingDiagnostic.model_validate(diagnostic).model_dump()
    db.execute("INSERT INTO runtime_mapping_diagnostics(body) VALUES (?)", (json.dumps({
        "session_id": lease["mapping"]["session_id"], "observed_at": now,
        "diagnostic": safe, "stop_code": code, "production_writes": False}),))
