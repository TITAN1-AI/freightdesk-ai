"""Workspace/section mapping metadata. No private values or executable selectors."""

import hashlib
import json
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.core.config import ROOT
from executors.ascend_extension.controller import Strict
from executors.ascend_extension.native import canonical

SCOPE = json.loads((ROOT / "extensions/ascend-x1/mapping-scope.json").read_text(encoding="utf-8"))
SECTIONS = SCOPE["sections"] + ["DISCOVERED_UNCLASSIFIED"]
FIELDS = set(SCOPE["fields"].values()) | {"UNKNOWN"}
MAP_OPERATION = "ASCEND_MAP_WORKSPACE"
AUTO_OPERATION = "ASCEND_MAP_NAVIGATE_SECTION"
MAPPING_ERRORS = frozenset({'STOPS_AUTHORITY_REQUIRED','STOPS_SCOPE_DENIED','STOPS_TABLE_BOUND','STOPS_TABLE_AMBIGUOUS','STOPS_HEADER_INVALID','STOPS_HEADER_DUPLICATE','STOPS_ROW_BOUND','STOPS_ROW_HIDDEN','STOPS_ROW_INVALID','STOPS_ACTION_AMBIGUOUS','STOPS_CONTROL_BOUND','STOPS_CONTAINMENT_INVALID','STOPS_ACTUAL_AMBIGUOUS',"CURRENT_LOAD_CAPTURE_NOT_DISPATCHED", "CAPTURE_ACKNOWLEDGEMENT_TIMEOUT", "WORKSPACE_CAPTURE_TIMEOUT", "SESSION_PROOF_TIMEOUT", "NO_FOREGROUND_ASCEND_WORKSPACE", "EXPECTED_LOAD_NOT_OPEN", "STARTING_SECTION_MISMATCH", "NOT_A_LOAD_WORKSPACE", "WORKSPACE_IDENTITY_MISSING", "WORKSPACE_IDENTITY_CONFLICT", "WORKSPACE_AMBIGUOUS",
    "WORKSPACE_CHANGED", "WORKSPACE_SECTION_UNVERIFIED", "WORKSPACE_SCOPE_DENIED", "WORKSPACE_BOUND",
    "MAPPING_NOT_ENABLED", "MAPPING_CAPTURE_BOUND", "MAPPING_CAPTURE_PENDING", "MAPPING_SESSION_CONSUMED",
    "MAPPING_CONTRACT_INVALID", "MAPPING_PAYLOAD_BOUND", "MAPPING_COMPLETE", "MAPPING_VALIDATION_REQUIRED",
    "MAPPING_WORKSPACE_BOUND", "MAPPING_SECTION_BOUND", "MAPPING_CONTRACT_BOUND", "MAPPING_OWNER_NOT_PRESENT",
    "NAVIGATION_CONTRACT_UNVERIFIED", "NAVIGATION_CONTROL_AMBIGUOUS", "NAVIGATION_CONTROL_CHANGED", "AUTO_MAP_SECTION_UNVERIFIED"})


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class MappingSessionApproval(Strict):
    orchestrator_job_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    authority_expires_at: float | None = Field(default=None, gt=0)
    orchestrated: bool = False
    causal_trace: bool = False
    session_only: bool = False
    capture_load_id: str | None = Field(default=None, pattern=r"^[0-9]{1,20}$")
    capture_section: Literal["Load Basics"] | None = None

    session_id: str = Field(pattern=r"^owner-x1-mapping-[a-zA-Z0-9-]{1,64}$")
    mode: Literal["FIRST_VALIDATION", "NORMAL_OWNER_PRESENT"] = "FIRST_VALIDATION"
    operation_mode: Literal["OBSERVE", "AUTO_MAP"] = "OBSERVE"
    approved_load_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    minutes: int = Field(default=20, ge=1, le=30)
    max_captures: int = Field(default=120, ge=1, le=300)
    max_workspace_captures: int = Field(default=10, ge=1, le=30)
    max_section_observations: int = Field(default=60, ge=1, le=120)
    max_contract_observations: int = Field(default=1000, ge=1, le=3000)

    @field_validator("approved_load_ids")
    @classmethod
    def exact_sample(cls, values):
        if values is None:
            return None
        if len(set(values)) != len(values) or any(not v.isascii() or not v.isdigit() or not 1 <= len(v) <= 20 for v in values):
            raise ValueError("WORKSPACE_SCOPE_DENIED")
        return values

    @model_validator(mode="after")
    def first_cohort(self):
        if (self.capture_section is not None and self.capture_load_id is None
            or self.capture_load_id is not None and (self.operation_mode != "OBSERVE"
            or self.capture_load_id not in (self.approved_load_ids or []))):
            raise ValueError("WORKSPACE_SCOPE_DENIED")
        if self.mode == "FIRST_VALIDATION" and (self.approved_load_ids is None or not 3 <= len(self.approved_load_ids) <= 5):
            raise ValueError("WORKSPACE_SCOPE_DENIED")
        return self


class MappingCommand(Strict):
    capture_load_id: str | None = Field(default=None, pattern=r"^[0-9]{1,20}$")
    capture_section: Literal["Load Basics"] | None = None

    version: Literal[1] = 1
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    operation: Literal["ASCEND_MAP_WORKSPACE"] = MAP_OPERATION
    tenant_id: Literal["booking-logistics"] = "booking-logistics"
    actor: Literal["FreightDesk/Avery"] = "FreightDesk/Avery"
    load_id: None = None
    expected_revision: None = None
    approved_load_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    owner_present: bool = False
    lease_expires_at: float = Field(ge=0)

    _sample = field_validator("approved_load_ids")(MappingSessionApproval.exact_sample.__func__)


class NavigationCandidate(Strict):
    section: str
    tag: Literal["button", "a"]
    role: Literal["tab"]
    control_type: Literal["button", "anchor"]
    reference: Literal["ARIA_CONTROLS", "FRAGMENT", "DATA_TARGET", "LABELLEDBY"]
    relative_path: list[int] = Field(max_length=12)
    target_relative_path: list[int] = Field(max_length=12)
    same_document_target: Literal[True]
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def safe(self):
        if (self.section not in SCOPE["sections"] or any(type(i) is not int or not 0 <= i <= 10000 for i in self.relative_path + self.target_relative_path)
            or self.control_type != ("button" if self.tag == "button" else "anchor")
            or fingerprint(self.model_dump(exclude={"fingerprint"})) != self.fingerprint):
            raise ValueError("NAVIGATION_CONTRACT_UNVERIFIED")
        return self


class VerifiedSectionNavigation(Strict):
    candidate: NavigationCandidate
    classification: Literal["READ_ONLY_NAVIGATION"]
    confidence: Literal["VERIFIED"]
    workspace_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_map_version: int = Field(ge=1)
    review_source: Literal["OWNER_REVIEWED_PROVIDER_NAVIGATION"]


class AutoMapNavigationCommand(MappingCommand):
    operation: Literal["ASCEND_MAP_NAVIGATE_SECTION"] = AUTO_OPERATION
    load_id: str = Field(pattern=r"^[0-9]{1,20}$")
    navigation: VerifiedSectionNavigation
    expected_from_section: str
    return_to_start: bool

    @field_validator("expected_from_section")
    @classmethod
    def safe_section(cls, value):
        if value not in SCOPE["sections"]:
            raise ValueError("AUTO_MAP_SECTION_UNVERIFIED")
        return value


class WorkspaceIdentitySignal(Strict):
    kind: Literal["HEADER_CONTROL", "BREADCRUMB", "ROUTE_ID", "PROVIDER_ATTRIBUTE"]
    load_id: str = Field(pattern=r"^[0-9]{1,20}$")
    outside_child_section: Literal[True]


class AscendLoadWorkspaceContract(Strict):
    contract: Literal["AscendLoadWorkspaceContract"]
    provider: Literal["AscendTMS"]
    entity_type: Literal["LOAD"]
    source: Literal["provider DOM"]
    load_id: str = Field(pattern=r"^[0-9]{1,20}$")
    confidence: Literal["VERIFIED"]
    signals: list[WorkspaceIdentitySignal] = Field(min_length=1, max_length=16)
    section_controls: list[str] = Field(min_length=2, max_length=13)
    navigation_candidates: list[NavigationCandidate] = Field(default_factory=list, max_length=13)
    path_pattern: str = Field(pattern=r"^/(?:loads?|:load_id|:segment)?(?:/(?:loads?|:load_id|:segment)){0,7}$")
    observed_at: float = Field(ge=0)
    shell_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    tenant_identity_source: Literal["OWNER_ATTESTED"]

    @model_validator(mode="after")
    def proof(self):
        if (any(s.load_id != self.load_id for s in self.signals)
            or len(set(self.section_controls)) != len(self.section_controls)
            or any(s not in SCOPE["sections"] for s in self.section_controls)):
            raise ValueError("WORKSPACE_IDENTITY_CONFLICT")
        structure = {"signals": sorted(set(s.kind for s in self.signals)), "sections": self.section_controls}
        if fingerprint(structure) != self.shell_fingerprint:
            raise ValueError("MAPPING_CONTRACT_INVALID")
        return self


class MappingLocatorGraph(Strict):
    signals: list[Literal["LABEL_CONTROL", "ARIA_LABEL", "ARIA_LABELLEDBY", "PROVIDER_ATTRIBUTE", "NEIGHBOR", "CONTROL_ROLE"]] = Field(max_length=6)
    relative_path: list[int] = Field(max_length=12)
    neighboring_labels: list[str] = Field(max_length=4)
    data_attribute_names: list[str] = Field(max_length=8)
    aria_relationships: list[Literal["labelledby", "describedby", "controls"]] = Field(max_length=3)

    @model_validator(mode="after")
    def safe(self):
        if (any(n not in SCOPE["data_attributes"] + ["data-unclassified"] for n in self.data_attribute_names)
            or any(n not in SCOPE["fields"] for n in self.neighboring_labels)
            or any(type(n) is not int or not 0 <= n <= 10000 for n in self.relative_path)):
            raise ValueError("MAPPING_CONTRACT_INVALID")
        return self


class AscendFieldContract(Strict):
    field_name_candidate: str
    section: str
    semantic_label: str
    control_type: Literal["text", "tel", "email", "number", "date", "time", "datetime-local", "checkbox", "select", "textarea", "output", "STATIC", "OTHER"]
    editable: bool
    role: Literal["textbox", "combobox", "checkbox", "status", "OTHER"]
    locator_graph: MappingLocatorGraph
    evidence_level: Literal["LEVEL_1", "LEVEL_2", "LEVEL_3"] | None
    confidence: Literal["PROPOSED", "UNKNOWN"]
    presence: Literal["VISIBLE"]
    optionality: Literal["UNKNOWN"]
    observed_on_load: str = Field(pattern=r"^[0-9]{1,20}$")
    observed_at: float = Field(ge=0)
    contract_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")

    def structure(self):
        return self.model_dump(exclude={"observed_on_load", "observed_at", "contract_fingerprint", "presence", "optionality"})

    @model_validator(mode="after")
    def classification(self):
        if (self.field_name_candidate not in FIELDS or self.section not in SECTIONS
            or self.semantic_label not in SCOPE["fields"] and self.semantic_label != "UNCLASSIFIED_LABEL"):
            raise ValueError("MAPPING_CONTRACT_INVALID")
        signals = self.locator_graph.signals
        if (self.field_name_candidate != "UNKNOWN" and self.semantic_label != "UNCLASSIFIED_LABEL"
            and SCOPE["fields"][self.semantic_label] != self.field_name_candidate):
            raise ValueError("MAPPING_CONTRACT_INVALID")
        level = None if self.field_name_candidate == "UNKNOWN" else "LEVEL_1" if "PROVIDER_ATTRIBUTE" in signals else "LEVEL_2" if set(signals) & {"LABEL_CONTROL", "ARIA_LABEL", "ARIA_LABELLEDBY"} else "LEVEL_3"
        if (self.evidence_level != level or self.confidence != ("PROPOSED" if level else "UNKNOWN")
            or fingerprint(self.structure()) != self.contract_fingerprint):
            raise ValueError("MAPPING_CONTRACT_INVALID")
        return self


STOP_HEADERS = ['Stop Order', 'Action(s)', 'Scheduled Date/Time', 'Actual Date/Time',
    'Location', 'Address', 'Private Notes', 'Cargo', 'Reference #', 'Show on', 'Reorder']


class StopActualSurface(Strict):
    present: Literal[True]
    evidence: Literal['PROVIDER_CLASS']
    value_semantics: Literal['CANDIDATE_ONLY']


class StopActualMetadata(Strict):
    arrival: StopActualSurface
    departure: StopActualSurface


class StopScheduledMetadata(Strict):
    surface_present: bool
    subtype: Literal['UNKNOWN']


class StopRowMetadata(Strict):
    capture_row_ref: int = Field(ge=0, lt=20)
    provider_row_key: None
    action: Literal['PICKUP', 'DELIVERY']
    control_count: int = Field(ge=0, le=20)
    scheduled: StopScheduledMetadata
    actual: StopActualMetadata


class StopsMetadata(Strict):
    headers: list[str] = Field(min_length=11, max_length=11)
    rows: list[StopRowMetadata] = Field(max_length=20)
    auxiliary_row_count: int = Field(ge=0, le=20)
    coverage: Literal['CURRENT_RENDERED_TABLE_ONLY']

    @model_validator(mode='after')
    def coherent(self):
        if (set(self.headers) != set(STOP_HEADERS)
            or len(self.rows) + self.auxiliary_row_count > 20
            or [r.capture_row_ref for r in self.rows] != list(range(len(self.rows)))):
            raise ValueError('MAPPING_CONTRACT_INVALID')
        return self


class AscendLoadSectionContract(Strict):
    contract: Literal["AscendLoadSectionContract"]
    section: str
    workspace_load_id: str = Field(pattern=r"^[0-9]{1,20}$")
    identity_source: Literal["INHERITED_FROM_REVALIDATED_WORKSPACE"]
    section_signal: Literal["SELECTED_CONTROL", "VISIBLE_HEADING", "SELECTED_ROUTE_AND_VISIBLE_HEADING"]
    headings: list[str] = Field(max_length=24)
    action_controls: list[str] = Field(max_length=32)
    fields: list[AscendFieldContract] = Field(max_length=64)
    coverage: Literal["CURRENT_VISIBLE_SECTION_ONLY"]
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    stops_metadata: StopsMetadata | None = None

    @model_validator(mode="after")
    def safe_structure(self):
        if (self.section not in SECTIONS or any(h not in SECTIONS + ["UNCLASSIFIED_LABEL"] for h in self.headings)
            or any(a not in SCOPE["actions"] + SCOPE["sections"] + ["UNCLASSIFIED_LABEL"] for a in self.action_controls)
            or any(f.section != self.section or f.observed_on_load != self.workspace_load_id for f in self.fields)):
            raise ValueError("MAPPING_CONTRACT_INVALID")
        structure = {"section": self.section, "headings": self.headings,
            "actions": self.action_controls, "fields": [f.contract_fingerprint for f in self.fields]}
        if self.stops_metadata is not None:
            if (self.section != 'Edit Stops' or self.fields
                or self.section_signal not in {'SELECTED_CONTROL', 'SELECTED_ROUTE_AND_VISIBLE_HEADING'}):
                raise ValueError('MAPPING_CONTRACT_INVALID')
            structure['stops_metadata'] = self.stops_metadata.model_dump()
        if self.fingerprint != fingerprint(structure):
            raise ValueError("MAPPING_CONTRACT_INVALID")
        return self


class AscendProviderMap(Strict):
    schema_version: Literal[1]
    provider: Literal["AscendTMS"]
    source: Literal["live extension DOM"]
    workspace: AscendLoadWorkspaceContract
    section: AscendLoadSectionContract
    revalidated_after_capture: Literal[True]
    activation: Literal["CANDIDATE_ONLY"]
    values_included: Literal[False]
    writes_allowed: Literal[False]
    owner_present: bool

    @model_validator(mode="after")
    def same_workspace(self):
        if (self.workspace.load_id != self.section.workspace_load_id
            or any(f.observed_at != self.workspace.observed_at for f in self.section.fields)):
            raise ValueError("WORKSPACE_CHANGED")
        return self


class AscendOperationalViewContract(Strict):
    """Prepared vocabulary only; independent of the live Active Loads parser."""
    view: Literal["PLANNING_LOADS", "ACTIVE_LOADS", "READY_FOR_ACCOUNTING"]
    provider_label: str
    status: Literal["PREPARED_NOT_LIVE_VALIDATED"] = "PREPARED_NOT_LIVE_VALIDATED"
    workflow_semantics: Literal["OWNER_ATTESTED_HYPOTHESIS"] = "OWNER_ATTESTED_HYPOTHESIS"

    @model_validator(mode="after")
    def label(self):
        if self.provider_label != {"PLANNING_LOADS": "Planning Loads", "ACTIVE_LOADS": "Active Loads", "READY_FOR_ACCOUNTING": "Ready for Accounting Loads"}[self.view]:
            raise ValueError("MAPPING_CONTRACT_INVALID")
        return self


OPERATIONAL_VIEW_SKELETONS = tuple(AscendOperationalViewContract(view=view, provider_label=label) for view, label in (
    ("PLANNING_LOADS", "Planning Loads"), ("ACTIVE_LOADS", "Active Loads"), ("READY_FOR_ACCOUNTING", "Ready for Accounting Loads")))
