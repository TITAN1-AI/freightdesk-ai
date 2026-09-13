"""Fixed persistent-runtime read vocabulary; no selectors, code, URLs or writes."""

from typing import Literal
from executors.ascend_extension.mapping_diagnostics import MappingDiagnostic

from pydantic import Field, field_validator, model_validator

from executors.ascend_extension.controller import Row, Strict
from executors.ascend_extension.board_schema import BoardSchemaDiagnostic
from executors.ascend_extension.detail_diagnostics import DetailContainerDiagnostic
from executors.ascend_extension.bridge_build import BridgeBuild, DocumentHandshake
from executors.ascend_extension.view_contract import AscendLoadBoardViewContract

RUNTIME_OPERATIONS = (
    "ASCEND_GET_SESSION_STATE",
    "ASCEND_NAVIGATE_ACTIVE_LOADS",
    "ASCEND_GET_ACTIVE_LOADS",
    "ASCEND_FIND_LOAD",
    "ASCEND_OPEN_LOAD_READONLY",
    "ASCEND_READ_LOAD",
    "ASCEND_READ_STOPS",
    "ASCEND_READ_ASSIGNMENT",
    "ASCEND_DISCOVER_DETAIL_CONTRACT",
)


class RuntimeRoute(Strict):
    tab_id: int = Field(ge=0)
    document_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    eligible_tab_count: int = Field(ge=1, le=100)
    origin: Literal["https://ascendtms.com"]
    path: Literal["/", "/loads", "/login.html", "OTHER"]


class RuntimeCommand(Strict):
    version: Literal[1] = 1
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    operation: Literal[
        "ASCEND_GET_SESSION_STATE",
        "ASCEND_NAVIGATE_ACTIVE_LOADS",
        "ASCEND_GET_ACTIVE_LOADS",
        "ASCEND_FIND_LOAD",
        "ASCEND_OPEN_LOAD_READONLY",
        "ASCEND_READ_LOAD",
        "ASCEND_READ_STOPS",
        "ASCEND_READ_ASSIGNMENT",
        "ASCEND_DISCOVER_DETAIL_CONTRACT",
    ]
    tenant_id: Literal["booking-logistics"] = "booking-logistics"
    actor: Literal["FreightDesk/Avery"] = "FreightDesk/Avery"
    load_id: str | None = Field(default=None, pattern=r"^[0-9]{1,20}$")
    expected_revision: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @field_validator("version", mode="before")
    @classmethod
    def exact_protocol(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("RUNTIME_SCOPE_INVALID")
        return value

    @model_validator(mode="after")
    def scope(self):
        if self.operation in RUNTIME_OPERATIONS[:3]:
            if self.load_id is not None or self.expected_revision is not None:
                raise ValueError("RUNTIME_SCOPE_INVALID")
        elif self.load_id is None or self.expected_revision is None:
            raise ValueError("RUNTIME_SCOPE_INVALID")
        return self


class RuntimeWake(Strict):
    mapping_hint: bool = False
    owner_present: bool | None = None
    build: BridgeBuild | None = None
    handshake: DocumentHandshake | None = None
    routing_error: Literal["CONTENT_SCRIPT_MISSING", "CONTENT_SCRIPT_OLD_VERSION", "CONTENT_SCRIPT_PORT_STALE", "DOCUMENT_CHANGED", "PROTOCOL_VERSION_MISMATCH", "CONTENT_SCRIPT_INJECTION_BLOCKED", "CONTENT_SCRIPT_RECOVERY_FAILED", "READ_EXECUTION_FAILED", "TAB_STATE_CHANGED", "READ_TIMEOUT", "TAB_DISCOVERY_FAILED", "READ_POLICY_BLOCKED", "NO_FOREGROUND_ASCEND_WORKSPACE"] | None = None
    kind: Literal["RUNTIME_WAKE"]
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    route: RuntimeRoute | None = None
    probe_only: bool = False
    routing_state: (
        Literal["WAITING_FOR_OWNER_WORKSPACE", "WAITING_FOR_ASCEND", "TAB_SELECTION_REQUIRED", "ASCEND_REAUTH_REQUIRED", "CONTENT_SCRIPT_STALE", "TAB_DISCOVERY_FAILED"] | None
    ) = None
    eligible_tab_count: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def routing_metadata(self):
        if self.owner_present is not None and self.route is None:
            raise ValueError("RUNTIME_SCOPE_INVALID")
        if self.build is not None and self.route is not None:
            if self.handshake is None or self.handshake.tab_id != self.route.tab_id or self.handshake.document_id != self.route.document_id:
                raise ValueError("DOCUMENT_CHANGED")
        if self.routing_error is not None and self.routing_state is None:
            raise ValueError("RUNTIME_SCOPE_INVALID")
        if self.routing_state is not None and (self.route is not None or self.probe_only):
            raise ValueError("RUNTIME_SCOPE_INVALID")
        if self.eligible_tab_count is not None and self.routing_state is None:
            raise ValueError("RUNTIME_SCOPE_INVALID")
        if self.routing_state == "WAITING_FOR_ASCEND" and self.eligible_tab_count not in (None, 0):
            raise ValueError("RUNTIME_SCOPE_INVALID")
        return self


class RuntimeResult(Strict):
    build: BridgeBuild | None = None
    kind: Literal["RUNTIME_RESULT"]
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    command_request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    route: RuntimeRoute
    evidence: dict | None
    error_code: str | None


class RuntimeViewEvidence(Strict):
    detail_container_diagnostic: DetailContainerDiagnostic | None = None
    schema_diagnostic: BoardSchemaDiagnostic | None = None
    view_contract: AscendLoadBoardViewContract


class RuntimeBoardEvidence(Strict):
    schema_diagnostic: BoardSchemaDiagnostic | None = None
    view_contract: AscendLoadBoardViewContract
    source_view: Literal["ACTIVE_LOADS"]
    coverage: Literal["VISIBLE_BOARD_ONLY"]
    rows: list[Row] = Field(max_length=100)
    board_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def no_failed_schema(self):
        if self.schema_diagnostic is not None and self.schema_diagnostic.failed_predicate is not None:
            raise ValueError("BOARD_SCHEMA_INVALID")
        return self


class UnknownDetailEvidence(Strict):
    """Unverified field contracts cannot acquire provider values through a read lease."""

    view_contract: AscendLoadBoardViewContract
    load_id: str = Field(pattern=r"^[0-9]{1,20}$")
    board_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    mapping_state: Literal["UNKNOWN"]
    fields: list = Field(max_length=0)


class RuntimeMappingProgress(Strict):
    kind: Literal["RUNTIME_MAPPING_PROGRESS"]
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    command_request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    route: RuntimeRoute
    diagnostic: MappingDiagnostic


class RuntimeCaptureAck(Strict):
    kind: Literal["RUNTIME_CAPTURE_ACK"]
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    command_request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    route: RuntimeRoute
