r"""Desired-behavior offline regressions for the mapping reliability correction.

Run: .\.tools\python\python.exe -B -m scripts.review_x1_mapping_state
Uses synthetic metadata, fake access, and SQLite :memory: exclusively. No runtime
repository, host, browser, lease, credential, or provider operation is initialized.
Assertions require corrected behavior; no vendor behavior is claimed.
"""

import json
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

from executors.ascend_extension.mapping_orchestrator import MappingIntent, MappingOrchestrator
from executors.ascend_extension.mapping_store import persist_map
from executors.ascend_extension.workspace_contracts import MappingSessionApproval, fingerprint


def synthetic_map(load_id, *, optional_field=False):
    """Valid metadata only; synthetic IDs and no operational field values."""
    section = "Load Basics"
    fields = []
    labels = [("equipment", "Equipment")]
    if optional_field:
        labels.append(("carrier", "Carrier"))
    for index, (name, label) in enumerate(labels):
        structure = dict(
            field_name_candidate=name, section=section, semantic_label=label,
            control_type="text", editable=True, role="OTHER",
            locator_graph=dict(signals=["LABEL_CONTROL"], relative_path=[index],
                neighboring_labels=[], data_attribute_names=[], aria_relationships=[]),
            evidence_level="LEVEL_2", confidence="PROPOSED",
        )
        fields.append(dict(structure, presence="VISIBLE", optionality="UNKNOWN",
            observed_on_load=load_id, observed_at=1000.0,
            contract_fingerprint=fingerprint(structure)))
    controls = ["Load Basics", "Customer Info"]
    workspace = dict(
        contract="AscendLoadWorkspaceContract", provider="AscendTMS", source="provider DOM",
        entity_type="LOAD", load_id=load_id, confidence="VERIFIED",
        signals=[dict(kind="HEADER_CONTROL", load_id=load_id, outside_child_section=True)],
        section_controls=controls, path_pattern="/loads", observed_at=1000.0,
        shell_fingerprint=fingerprint(dict(signals=["HEADER_CONTROL"], sections=controls)),
        tenant_identity_source="OWNER_ATTESTED",
    )
    child = dict(
        contract="AscendLoadSectionContract", section=section, workspace_load_id=load_id,
        identity_source="INHERITED_FROM_REVALIDATED_WORKSPACE", section_signal="SELECTED_CONTROL",
        headings=[section], action_controls=["Save"], fields=fields,
        coverage="CURRENT_VISIBLE_SECTION_ONLY",
        fingerprint=fingerprint(dict(section=section, headings=[section], actions=["Save"],
            fields=[field["contract_fingerprint"] for field in fields])),
    )
    return dict(schema_version=1, provider="AscendTMS", source="live extension DOM",
        workspace=workspace, section=child, revalidated_after_capture=True,
        activation="CANDIDATE_ONLY", values_included=False, writes_allowed=False, owner_present=True)


def check_cross_load_variation():
    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE TABLE runtime_provider_maps(id INTEGER PRIMARY KEY, body TEXT)")
        approval = MappingSessionApproval(session_id="owner-x1-mapping-memory-review",
            approved_load_ids=["900101", "900102", "900103"])
        lease = {"mapping": approval.model_dump()}
        state = {}
        pending = {"deadline": 1012.0, "route": {"document_id": "f" * 32}}
        first = persist_map(db, state, lease, pending,
            synthetic_map("900101", optional_field=True), 1000.0)
        second = persist_map(db, state, lease, pending, synthetic_map("900102"), 1000.0)
        orchestrator = object.__new__(MappingOrchestrator)
        orchestrator._records = lambda job: ([second], [])
        orchestrator._stage = lambda *args: None
        orchestrator.access = SimpleNamespace(status=lambda: {})
        job = dict(session_ids=[], processed_versions=[],
            intent=MappingIntent(scope="OWNER_NAVIGATION_OBSERVE").model_dump(),
            active_load=None, maps=[], observed_ids=[], cycles=[])
        orchestrator._consume_maps(None, job)
        assert first["structural_drift"] is False
        assert second["structural_drift"] is False
        assert second["change_kind"] == "CROSS_LOAD_VARIATION"
        assert job["await_owner_change"] is True
        return dict(case="cross_load_optional_field_variation", passed=True,
            first_drift=False, second_drift=False, change_kind=second["change_kind"], stop_code=None)
    finally:
        db.close()


class MemoryOrchestrator(MappingOrchestrator):
    """Exercise real start/tick/control logic without constructing RuntimeAccess."""

    def __init__(self, access):
        self.access = access
        self.clock = lambda: 1000.0
        self.path = SimpleNamespace(exists=lambda: True)
        self.memory = sqlite3.connect(":memory:")
        self.memory.executescript("""
            CREATE TABLE jobs(id TEXT PRIMARY KEY, body TEXT);
            CREATE TABLE events(seq INTEGER PRIMARY KEY, job_id TEXT, body TEXT);
        """)

    @contextmanager
    def database(self, *, readonly=False):
        with self.memory:
            yield self.memory


def check_read_job_wait():
    status = dict(read_access="ENABLED", mapping_mode=False, state="READ_ONLY_READY",
        extension="CONNECTED", native_host="CONNECTED", pairing="VALID", paused=False,
        eligible_tab_count=1, mapping_session_id=None, error_code=None, session="UNKNOWN")
    access = SimpleNamespace(_owner=lambda flag: None, status=lambda: dict(status),
        gate=lambda repository: None, enrollment_guard=lambda: None, repo=None,
        path=SimpleNamespace(exists=lambda: False), notify_mapping_job=lambda: None, causal_event=lambda event, **kwargs: None)
    disabled = []
    def enable(*, mapping, owner_authorized, expected_previous_generation=None):
        status.update(read_access="ENABLED", mapping_mode=True, mapping_session_id=mapping.session_id, state="MAPPING_READY")
    access.enable = enable
    access.disable = lambda **kw: disabled.append(True)
    orchestrator = MemoryOrchestrator(access)
    try:
        initial = orchestrator.start(owner_authorized=True)
        status.update(read_access="REVOKED", state="STOPPED")
        after = orchestrator.tick()
        repeated = orchestrator.start(owner_authorized=True)
        resumed = orchestrator.control("resume", owner_authorized=True)
        assert initial["owner_action"] == "READ_JOB_ACTIVE"
        assert initial["stage"] == "WAITING_FOR_READ_JOB"
        assert all(item["stage"] == "WAITING_FOR_OWNER_WORKSPACE" for item in (after, repeated, resumed))
        assert disabled == []
        return dict(case="completed_unrelated_read_job", passed=True,
            initial_action=initial["owner_action"], after_board_revoke=after["stage"],
            repeated_start=repeated["stage"], resume=resumed["stage"])
    finally:
        orchestrator.memory.close()


def main():
    print(json.dumps(dict(audit="MAPPING_RELIABILITY_REGRESSIONS", product_success_test=True,
        synthetic_evidence=True, storage="SQLITE_MEMORY_ONLY", live_execution=False,
        production_writes=False)))
    for result in (check_read_job_wait(), check_cross_load_variation()):
        print(json.dumps(result))


if __name__ == "__main__":
    main()
