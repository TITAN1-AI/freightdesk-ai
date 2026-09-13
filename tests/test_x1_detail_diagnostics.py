"""Per-attempt, structural-only failure reporting and host persistence fixtures."""

import json

import pytest
from pydantic import ValidationError

from executors.ascend_extension.detail_diagnostics import BOUNDS, DetailContainerDiagnostic
from scripts.ascend_x1_detail import report
from tests.test_ascend_detail_contract import ATTEMPT, prepare
from tests.test_ascend_x1_controller import repo as repo, view_contract
from tests.test_ascend_x1_runtime import result, runtime as runtime, wake


def diagnostic(category="direct_targets"):
    count = BOUNDS[category] + 1
    return dict(version=1, stage="BEFORE_CLICK" if category in {"direct_targets", "opener_attributes"} else "DOM_DIFF",
                click_dispatched=category not in {"direct_targets", "opener_attributes"}, row_verified=True, opener_verified=True,
                baseline_container_count=80, ignored_unchanged_count=80, candidate_count=0,
                categories=dict(dialogs=0, panels=0, forms=0, tabs=0, other=0),
                counts={k: count if k == category else 0 for k in BOUNDS}, limits=BOUNDS,
                ranked_candidates=[], selected_level=None, failed_category=category, measured=count, maximum=BOUNDS[category])


@pytest.mark.parametrize("category", list(BOUNDS))
def test_safe_category_failure_is_scoped_and_retained_after_disable(runtime, category):
    access, controller, *_ = runtime
    dispatch = prepare(runtime)
    code = "DETAIL_BOUND_" + category.upper()
    response = controller.finish(result(dispatch, {"view_contract": view_contract(), "detail_container_diagnostic": diagnostic(category)}, code))
    assert response["status"]["error_code"] == code
    assert response["status"]["detail_container_diagnostic"] == diagnostic(category)
    assert "command" not in wake(controller)
    access.disable(owner_authorized=True)
    output = report(access, ATTEMPT)
    assert output["error_code"] == code
    assert output["execution_stage"] == "ASCEND_OPEN_LOAD_READONLY"
    assert output["detail_container_diagnostic"] == diagnostic(category)
    assert output["attempt_consumed"] and not output["production_writes"]
    assert report(access, "not-queued")["error_code"] is None
    with access.database(readonly=True) as db:
        receipts = [json.loads(r[0]) for r in db.execute("SELECT body FROM runtime_receipts")]
        events = [json.loads(r[0]) for r in db.execute("SELECT body FROM runtime_events")]
        assert db.execute("SELECT COUNT(*) FROM runtime_detail_contracts").fetchone()[0] == 0
    assert any(r.get("attempt_id") == ATTEMPT and r.get("error_code") == code for r in receipts)
    assert any(e.get("detail_container_diagnostic") == diagnostic(category) for e in events)


@pytest.mark.parametrize("change", ["raw", "category", "measurement", "limits", "rank"])
def test_structural_diagnostic_rejects_private_or_inconsistent_metadata(change):
    value = diagnostic()
    if change == "raw":
        value["raw_html"] = "PRIVATE"
    elif change == "category":
        value["failed_category"] = "PRIVATE"
    elif change == "measurement":
        value["measured"] = 0
    elif change == "limits":
        value["limits"] = {**BOUNDS, "direct_targets": 1000}
    else:
        value["ranked_candidates"] = [dict(level="A", score=400, reasons=["NEW_CONTAINER"], category="dialogs")]
    with pytest.raises(ValidationError):
        DetailContainerDiagnostic.model_validate(value)


def test_untrusted_diagnostic_not_saved_to_receipts_or_status(runtime):
    access, controller, *_ = runtime
    dispatch = prepare(runtime)
    response = controller.finish(result(dispatch, {"view_contract": view_contract(),
        "detail_container_diagnostic": {**diagnostic(), "secret": "PRIVATE"}}, "DETAIL_BOUND_DIRECT_TARGETS"))
    assert response["status"]["error_code"] == "DETAIL_BOUND_DIRECT_TARGETS"
    assert response["status"]["detail_container_diagnostic"] is None
    with access.database(readonly=True) as db:
        for table in ("runtime_receipts", "runtime_events", "runtime_state"):
            assert "PRIVATE" not in str(db.execute(f"SELECT * FROM {table}").fetchall())


def test_older_receipt_fallback_stops_at_next_attempt(runtime):
    access, controller, now, *_ = runtime
    dispatch = prepare(runtime)
    # Represent the legacy view-only failure without touching any real runtime data.
    controller.finish(result(dispatch, {"view_contract": view_contract()}, "DETAIL_BOUND_CONTAINERS"))
    with access.database() as db:
        receipt_id, raw = db.execute("SELECT id,body FROM runtime_receipts WHERE id=?", (dispatch["command"]["request_id"],)).fetchone()
        old = json.loads(raw)
        old.pop("attempt_id")
        # Runtime receipts have an update-prevention trigger; append a separate legacy fixture.
        db.execute("INSERT INTO runtime_receipts VALUES (?,?)", ("legacy", json.dumps(old)))
        now[0] += 100
        db.execute("INSERT INTO runtime_detail_attempts VALUES (?,?)", ("later", json.dumps({"queued_at": now[0]})))
        db.execute("INSERT INTO runtime_receipts VALUES (?,?)", ("later", json.dumps({"observed_at": now[0], "operation": "ASCEND_OPEN_LOAD_READONLY", "error_code": "DETAIL_IDENTITY_CONFLICT"})))
    assert report(access, ATTEMPT)["error_code"] == "DETAIL_BOUND_CONTAINERS"
