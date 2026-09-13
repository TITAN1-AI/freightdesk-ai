"""Offline host/metadata contracts, using only isolated runtime fixtures."""

import copy
import hashlib
import json
import sqlite3

import pytest
from pydantic import ValidationError

from executors.ascend_extension.detail_contract import AscendLoadDetailContract, SCOPE
from executors.ascend_extension.native import canonical
from executors.ascend_extension.runtime_contracts import RuntimeCommand
from scripts.ascend_x1_detail import report
from tests.test_ascend_x1_controller import repo as repo, view_contract
from tests.test_ascend_x1_runtime import board, cycle, result, runtime as runtime, wake
from tests.test_webbridge_detail import identity

ATTEMPT = "owner-x1-detail-fixture-01"


def observation(now=1000.0, path=0, strategy="LABEL_CONTROL"):
    fields = []
    for name, definition in SCOPE.items():
        candidates = []
        if name == "carrier":
            candidates = [dict(section=definition["section"], label="Carrier", strategy=strategy,
                               tag="input", control_type="text", role=None,
                               attribute_names=["id", "data-field"], relative_path=[path],
                               neighbor_labels=["Carrier"], value_present=True, conflicting=False)]
        level = "LEVEL_1" if name == "load_id" or name == "carrier" and strategy == "PROVIDER_ATTRIBUTE" else "LEVEL_2" if name == "carrier" and strategy == "LABEL_CONTROL" else "LEVEL_3" if name == "carrier" else None
        fields.append(dict(field=name, evidence_level=level, confidence="PROPOSED" if level == "LEVEL_3" else "VERIFIED" if level else "UNKNOWN",
                           presence="PRESENT" if level else "UNKNOWN", candidates=candidates))
    structure = [{"field": f["field"], "candidates": [{k: v for k, v in c.items() if k != "value_present"} for c in f["candidates"]]} for f in fields]
    return dict(schema_version=1, provider="AscendTMS", view="LOAD_DETAIL", source="live extension DOM",
                validation_load_id="42", observed_at=now, identity=identity("42", board()["board_hash"]), fields=fields,
                container_reasons=["NEW_CONTAINER"], contract_fingerprint=hashlib.sha256(canonical(structure)).hexdigest(),
                activation="CANDIDATE_ONLY", writes_allowed=False, values_included=False)


def prepare(runtime, attempt=ATTEMPT):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    cycle(controller)
    access.queue_discovery("42", attempt, owner_authorized=True)
    cycle(controller)
    dispatch = wake(controller)
    assert dispatch["command"]["operation"] == "ASCEND_FIND_LOAD"
    controller.finish(result(dispatch, dict(view_contract=view_contract(), load_id="42", exact_row=True, board_hash=board()["board_hash"])))
    dispatch = wake(controller)
    assert dispatch["command"]["operation"] == "ASCEND_OPEN_LOAD_READONLY"
    return dispatch


def complete(runtime, attempt=ATTEMPT, path=0):
    access, controller, now, *_ = runtime
    controller.finish(result(prepare(runtime, attempt), identity("42", board()["board_hash"])))
    dispatch = wake(controller)
    assert dispatch["command"]["operation"] == "ASCEND_DISCOVER_DETAIL_CONTRACT"
    response = controller.finish(result(dispatch, dict(view_contract=view_contract(), load_id="42", board_hash=board()["board_hash"], contract=observation(now[0], path))))
    return response


def test_single_load_discovery_stops_and_versions_append_only(runtime):
    access, controller, now, *_ = runtime
    response = complete(runtime)
    assert response["status"]["state"] == "STOPPED"
    assert response["status"]["error_code"] == "DETAIL_DISCOVERY_COMPLETE"
    assert "command" not in wake(controller)
    safe = report(access, ATTEMPT)
    assert safe["contract_version"] == 1 and safe["attempt_consumed"]
    assert safe["activation"] == "CANDIDATE_ONLY" and not safe["live_validated"]
    assert safe["values_included"] is False and safe["validation_load_id"] == "42"
    assert safe["identity_strategy"] == "PROVIDER_DETAIL_FIELD"
    assert safe["fields"]["carrier"]["mapping"] == "VERIFIED"
    assert "candidates" not in json.dumps(safe) and "PRIVATE" not in json.dumps(safe)
    now[0] += 1000
    complete(runtime, "owner-x1-detail-fixture-02", path=1)
    assert report(access, "owner-x1-detail-fixture-02")["contract_version"] == 2
    now[0] += 1000
    complete(runtime, "owner-x1-detail-fixture-03", path=1)
    assert report(access, "owner-x1-detail-fixture-03")["contract_version"] == 2
    with access.database(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM runtime_detail_contracts").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM runtime_detail_attempts").fetchone()[0] == 3
        operations = [json.loads(r[0])["operation"] for r in db.execute("SELECT body FROM runtime_events")]
    assert "ASCEND_READ_ASSIGNMENT" not in operations
    assert "ASCEND_READ_STOPS" not in operations
    with pytest.raises(sqlite3.IntegrityError), access.database() as db:
        db.execute("DELETE FROM runtime_detail_contracts")


def test_consumed_attempt_cannot_be_reused(runtime):
    access, controller, now, *_ = runtime
    complete(runtime)
    now[0] += 1000
    access.enable(owner_authorized=True)
    cycle(controller)
    with pytest.raises(PermissionError, match="DETAIL_ATTEMPT_CONSUMED"):
        access.queue_discovery("42", ATTEMPT, owner_authorized=True)


@pytest.mark.parametrize("code", ["DETAIL_IDENTITY_CONFLICT", "DETAIL_IDENTITY_MISSING", "READ_TIMEOUT", "TAB_STATE_CHANGED"])
def test_identity_failure_never_dispatches_mapping(runtime, code):
    access, controller, *_ = runtime
    dispatch = prepare(runtime)
    controller.finish(result(dispatch, None, code))
    assert "command" not in wake(controller)
    assert report(access, ATTEMPT)["attempt_consumed"]
    with access.database(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM runtime_detail_contracts").fetchone()[0] == 0


def test_revoke_during_discovery_rejects_receipt(runtime):
    access, controller, now, *_ = runtime
    controller.finish(result(prepare(runtime), identity("42", board()["board_hash"])))
    dispatch = wake(controller)
    access.disable(owner_authorized=True)
    with pytest.raises(PermissionError, match="READ_LEASE_REVOKED"):
        controller.finish(result(dispatch, dict(view_contract=view_contract(), load_id="42", board_hash=board()["board_hash"], contract=observation(now[0]))))
    assert report(access, ATTEMPT)["state"] == "NOT_OBSERVED"


def test_unknown_or_stale_board_cannot_queue(runtime):
    access, controller, now, *_ = runtime
    access.enable(owner_authorized=True)
    with pytest.raises(PermissionError):
        access.queue_discovery("42", ATTEMPT, owner_authorized=True)
    cycle(controller)
    with pytest.raises(PermissionError, match="EXACT_LOAD_MISSING"):
        access.queue_discovery("1755", ATTEMPT, owner_authorized=True)
    now[0] += 301
    with pytest.raises(PermissionError, match="BOARD_CHANGED"):
        access.queue_discovery("42", ATTEMPT, owner_authorized=True)


def test_changed_board_after_selection_stops_before_open(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    cycle(controller)
    access.queue_discovery("42", ATTEMPT, owner_authorized=True)
    response = cycle(controller, board(("42", "92")))
    assert response["status"]["error_code"] == "BOARD_CHANGED"
    assert "command" not in wake(controller)


def test_contract_persistence_and_receipt_are_atomic(runtime):
    access, controller, now, *_ = runtime
    controller.finish(result(prepare(runtime), identity("42", board()["board_hash"])))
    dispatch = wake(controller)
    with access.database() as db:
        db.execute("CREATE TRIGGER fixture_receipt_failure BEFORE INSERT ON runtime_receipts BEGIN SELECT RAISE(ABORT, 'fixture'); END")
    response = controller.finish(result(dispatch, dict(view_contract=view_contract(), load_id="42", board_hash=board()["board_hash"], contract=observation(now[0]))))
    assert response["status"]["state"] == "STOPPED"
    with access.database(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM runtime_detail_contracts").fetchone()[0] == 0


@pytest.mark.parametrize("strategy,level,confidence", [("PROVIDER_ATTRIBUTE", "LEVEL_1", "VERIFIED"), ("LABEL_CONTROL", "LEVEL_2", "VERIFIED"), ("NEIGHBOR", "LEVEL_3", "PROPOSED")])
def test_evidence_scoring(strategy, level, confidence):
    c = AscendLoadDetailContract.model_validate(observation(strategy=strategy))
    field = next(f for f in c.fields if f.field == "carrier")
    assert (field.evidence_level, field.confidence) == (level, confidence)


@pytest.mark.parametrize("change", ["raw_value", "finance", "weak_verified", "identity", "activation", "write", "hash", "raw_label"])
def test_contract_rejects_untrusted_promotions_and_private_data(change):
    c = observation()
    carrier = c["fields"][1]
    if change == "raw_value":
        carrier["value"] = "PRIVATE_PHONE"
    elif change == "finance":
        carrier["field"] = "income"
    elif change == "weak_verified":
        carrier["candidates"][0]["strategy"] = "NEIGHBOR"
    elif change == "identity":
        c["identity"]["observed_load_id"] = "999"
    elif change == "activation":
        c["activation"] = "ACTIVE"
    elif change == "write":
        c["writes_allowed"] = True
    elif change == "hash":
        c["contract_fingerprint"] = "0" * 64
    elif change == "raw_label":
        carrier["candidates"][0]["label"] = "PRIVATE_ADDRESS"
    with pytest.raises(ValidationError):
        AscendLoadDetailContract.model_validate(c)


@pytest.mark.parametrize("operation", ["SAVE", "SUBMIT", "ASCEND_ASSIGN_CARRIER", "OUTLOOK_SEND", "CARRIERVIEW_READ"])
def test_no_write_or_other_vendor_operation(operation):
    with pytest.raises(ValidationError):
        RuntimeCommand(request_id="a" * 32, operation=operation, load_id="42", expected_revision="b" * 64)


def test_no_model_or_selector_command_injection():
    with pytest.raises(ValidationError):
        RuntimeCommand(request_id="a" * 32, operation="ASCEND_DISCOVER_DETAIL_CONTRACT", load_id="42", expected_revision="b" * 64, selector="button.save")


def test_blueprint_json_and_browser_scope_match():
    from tests.test_ascend_x1_dom import EXT
    script = (EXT / "detail-scope.js").read_text(encoding="utf-8")
    assert json.loads(script.split("Object.freeze(", 1)[1].rsplit(");", 1)[0]) == SCOPE
    c = observation()
    before = copy.deepcopy(c)
    AscendLoadDetailContract.model_validate(c)
    assert c == before
