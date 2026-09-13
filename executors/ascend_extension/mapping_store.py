"""Append-only provider maps and conservative cross-load metadata comparisons."""

import json
from pydantic import ValidationError

from executors.ascend_extension.workspace_contracts import AscendProviderMap
from executors.ascend_extension.bridge_build import BUILD


def ensure_map_indexes(db):
    """Additive, evidence-preserving indexes; no provider-map rewrite or deletion."""
    for name, expressions in {
        'section': "json_extract(body,'$.map.section.section')",
        'load': "json_extract(body,'$.map.workspace.load_id')",
        'load_section': "json_extract(body,'$.map.workspace.load_id'),json_extract(body,'$.map.section.section')",
        'session': "json_extract(body,'$.session_id')",
    }.items():
        db.execute(f'CREATE INDEX IF NOT EXISTS runtime_maps_{name} ON runtime_provider_maps({expressions},id)')


def _latest(db, predicate='', parameters=()):
    row = db.execute('SELECT body FROM runtime_provider_maps ' + predicate + ' ORDER BY id DESC LIMIT 1', parameters).fetchone()
    return json.loads(row[0]) if row else None


def _bounded_records(cursor, maximum=4096):
    rows = cursor.fetchmany(maximum + 1)
    if len(rows) > maximum:
        raise PermissionError('MAPPING_REPORT_BOUND')
    return [json.loads(row[0]) for row in rows]


def _workspace_structure(workspace):
    """Identity/navigation topology only, excluding the changing provider entity ID."""
    return {key: workspace.get(key) for key in ("shell_fingerprint", "navigation_candidates", "path_pattern")}


def _section_structure(section):
    return {key: section.get(key) for key in ("section", "section_signal", "headings", "action_controls")}


def persist_map(db, state, lease, pending, raw, now):
    try:
        observed = AscendProviderMap.model_validate(raw)
    except ValidationError:
        raise PermissionError("MAPPING_CONTRACT_INVALID") from None
    approval = lease["mapping"]
    if ((approval["approved_load_ids"] is not None and observed.workspace.load_id not in approval["approved_load_ids"])
        or approval["mode"] == "NORMAL_OWNER_PRESENT" and not observed.owner_present
        or not pending["deadline"] - 12 <= observed.workspace.observed_at <= now + 2):
        raise PermissionError("WORKSPACE_SCOPE_DENIED")
    if approval.get("capture_load_id") and (observed.workspace.load_id != approval["capture_load_id"] or approval.get("capture_section") is not None and observed.section.section != approval["capture_section"]):
        raise PermissionError("WORKSPACE_SCOPE_DENIED")
    last = state.get("mapping_last")
    workspace_change = (last is None or last["document_id"] != pending["route"]["document_id"] or last["load_id"] != observed.workspace.load_id)
    workspace_structure = _workspace_structure(observed.workspace.model_dump())
    unchanged = (last is not None and not workspace_change and last["section"] == observed.section.section
        and last.get("fingerprint") == observed.section.fingerprint and last.get("workspace_structure") == workspace_structure)
    if approval["mode"] == "NORMAL_OWNER_PRESENT" and unchanged:
        return None  # Unchanged sampling never duplicates provider-map versions or consumes observation budgets.
    if state.get("mapping_workspace_count", 0) + int(workspace_change) > approval["max_workspace_captures"]:
        raise PermissionError("MAPPING_WORKSPACE_BOUND")
    if state.get("mapping_section_count", 0) >= approval["max_section_observations"]:
        raise PermissionError("MAPPING_SECTION_BOUND")
    if state.get("mapping_contract_count", 0) + len(observed.section.fields) > approval["max_contract_observations"]:
        raise PermissionError("MAPPING_CONTRACT_BOUND")
    ensure_map_indexes(db)
    newest = _latest(db)
    prior = _latest(db, "WHERE json_extract(body,'$.map.section.section')=?", (observed.section.section,))
    changed = prior is not None and prior["map"]["section"]["fingerprint"] != observed.section.fingerprint
    same_load = _latest(db, "WHERE json_extract(body,'$.map.workspace.load_id')=? AND json_extract(body,'$.map.section.section')=?", (observed.workspace.load_id, observed.section.section))
    comparison = same_load or prior
    previous_workspace = _latest(db, "WHERE json_extract(body,'$.map.workspace.load_id')=?", (observed.workspace.load_id,)) or newest
    safety_drift = (previous_workspace is not None and _workspace_structure(previous_workspace["map"]["workspace"]) != workspace_structure
        or comparison is not None and _section_structure(comparison["map"]["section"]) != _section_structure(observed.section.model_dump()))
    same_load_drift = same_load is not None and same_load["map"]["section"]["fingerprint"] != observed.section.fingerprint
    drift = bool(safety_drift or same_load_drift)
    variation = bool(changed and same_load is None and not drift)
    change_kind = "STRUCTURAL_DRIFT" if drift else "CROSS_LOAD_VARIATION" if variation else "UNCHANGED" if prior else "FIRST_OBSERVATION"
    version = 1 if prior is None else prior["section_contract_version"] + int(changed)
    workspace_version = 1 if newest is None else newest["workspace_contract_version"] + int(
        newest["map"]["workspace"]["shell_fingerprint"] != observed.workspace.shell_fingerprint)
    navigation = ("FIRST_OBSERVATION" if last is None else "DOCUMENT_REPLACED" if last["document_id"] != pending["route"]["document_id"]
                  else "WORKSPACE_CHANGED" if last["load_id"] != observed.workspace.load_id else "DYNAMIC_SECTION_CHANGE"
                  if last["section"] != observed.section.section else "STABLE_CAPTURE")
    next_version = db.execute('SELECT coalesce(max(id),0)+1 FROM runtime_provider_maps').fetchone()[0]
    record = {"provider_map_version": next_version, "workspace_contract_version": workspace_version, "section_contract_version": version, "build": BUILD,
              "session_id": approval["session_id"], "navigation": navigation, "structural_drift": drift,
              "change_kind": change_kind, "cross_load_variation": variation,
              "map": observed.model_dump(), "live_validated": False, "production_writes": False}
    db.execute("INSERT INTO runtime_provider_maps(body) VALUES (?)", (json.dumps(record),))
    state["mapping_workspace_count"] = state.get("mapping_workspace_count", 0) + int(workspace_change)
    state["mapping_section_count"] = state.get("mapping_section_count", 0) + 1
    state["mapping_contract_count"] = state.get("mapping_contract_count", 0) + len(observed.section.fields)
    state["mapping_last"] = {"document_id": pending["route"]["document_id"], "load_id": observed.workspace.load_id, "section": observed.section.section, "fingerprint": observed.section.fingerprint, "workspace_structure": workspace_structure}
    state["mapping_last_summary"] = {"provider_map_version": record["provider_map_version"], "section_contract_version": version,
        "load_id": observed.workspace.load_id, "section": observed.section.section, "navigation": navigation,
        "field_count": len(observed.section.fields), "structural_drift": drift, "change_kind": change_kind, "cross_load_variation": variation}
    return record


def require_mapping_validation(db):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_mapping_validations'").fetchone():
        raise PermissionError("MAPPING_VALIDATION_REQUIRED")
    row = db.execute("SELECT body FROM runtime_mapping_validations WHERE json_extract(body,'$.operation_mode')='AUTO_MAP' ORDER BY rowid DESC LIMIT 1").fetchone()
    if not row or json.loads(row[0]).get("mapper_version") != 1 or json.loads(row[0]).get("operation_mode") != "AUTO_MAP":
        raise PermissionError("MAPPING_VALIDATION_REQUIRED")


def record_mapping_validation(access, session_id, *, owner_authorized=False):
    """Explicit owner review receipt, never inferred from a successful metadata capture."""
    access._owner(owner_authorized)
    report = report_maps(access, session_id)
    if report["state"] != "MAPPING_OBSERVED":
        raise PermissionError("MAPPING_VALIDATION_REQUIRED")
    with access.database() as db:
        row = db.execute("SELECT body FROM runtime_mapping_sessions WHERE id=?", (session_id,)).fetchone()
        approval = json.loads(row[0]) if row else None
        cycles = [json.loads(r[0]) for r in db.execute("SELECT body FROM runtime_auto_map_cycles WHERE json_extract(body,'$.session_id')=?", (session_id,))]
        if (not approval or approval["mode"] != "FIRST_VALIDATION"
            or set(report.get("loads_observed", [])) != set(approval["approved_load_ids"])
            or len(report.get("sections_observed", [])) < 2
            or not any(v["navigation"] == "DYNAMIC_SECTION_CHANGE" for v in report["versions"])
            or not any(p["loads_sampled"] >= 3 for p in report["cross_load_patterns"])):
            raise PermissionError("MAPPING_VALIDATION_REQUIRED")
        if approval["operation_mode"] == "AUTO_MAP" and (set(c["load_id"] for c in cycles if c["returned_to_start"]) != set(approval["approved_load_ids"])):
            raise PermissionError("MAPPING_VALIDATION_REQUIRED")
        receipt = {"mapper_version": 1, "session_id": session_id, "reviewed_at": access.clock(),
            "operation_mode": approval["operation_mode"],
            "review_source": "OWNER_CONFIRMED_CONTROLLED_VALIDATION", "normal_auto_map_qualified": approval["operation_mode"] == "AUTO_MAP",
            "field_read_mappings_activated": False, "production_writes": False}
        db.execute("INSERT INTO runtime_mapping_validations VALUES (?,?)", (session_id, json.dumps(receipt)))
    return receipt


def report_maps(access, session_id):
    if not access.path.exists():
        return {"state": "NOT_OBSERVED", "production_writes": False}
    with access.database(readonly=True) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_provider_maps'").fetchone():
            return {"state": "NOT_OBSERVED", "production_writes": False}
        diagnostics = _bounded_records(db.execute("SELECT body FROM runtime_mapping_diagnostics WHERE json_extract(body,'$.session_id')=? ORDER BY id LIMIT 4097", (session_id,))) if db.execute("SELECT 1 FROM sqlite_master WHERE name='runtime_mapping_diagnostics'").fetchone() else []
        records = _bounded_records(db.execute("SELECT body FROM runtime_provider_maps WHERE json_extract(body,'$.session_id')=? ORDER BY id LIMIT 4097", (session_id,)))
        cycles = _bounded_records(db.execute("SELECT body FROM runtime_auto_map_cycles WHERE json_extract(body,'$.session_id')=? ORDER BY id LIMIT 4097", (session_id,))) if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_auto_map_cycles'").fetchone() else []
    maps = [AscendProviderMap.model_validate(r["map"]) for r in records]
    sections = {}
    for m in maps:
        # A later capture of the same section/load supersedes only this comparison, never stored evidence.
        sections.setdefault(m.section.section, {})[m.workspace.load_id] = m
    differences = []
    for name, samples in sections.items():
        keys = set(f.field_name_candidate for m in samples.values() for f in m.section.fields) - {"UNKNOWN"}
        for key in sorted(keys):
            count = sum(any(f.field_name_candidate == key for f in m.section.fields) for m in samples.values())
            differences.append({"section": name, "field": key, "loads_sampled": len(samples), "loads_observed": count,
                "presence_pattern": "OBSERVED_IN_ALL_SAMPLED_CAPTURES" if count == len(samples) else "POSSIBLY_OPTIONAL_OR_CONDITIONAL",
                "confidence": "PROPOSED", "coverage": "CURRENT_VISIBLE_SECTION_ONLY"})
    return {"state": "MAPPING_OBSERVED" if maps else "NOT_OBSERVED", "session_id": session_id,
        "auto_map_cycles": cycles, "capture_diagnostics": diagnostics,
        "navigation_review_candidates": [{"provider_map_version": r["provider_map_version"], "load_id": m.workspace.load_id,
            "captured_section": m.section.section, "section_signal": m.section.section_signal, "navigation": r["navigation"],
            "candidates": [c.model_dump() for c in m.workspace.navigation_candidates], "confidence": "PROPOSED"} for r, m in zip(records, maps, strict=True)],
        "captures": len(maps), "loads_observed": sorted({m.workspace.load_id for m in maps}),
        "versions": [{**{k: r[k] for k in ("provider_map_version", "section_contract_version", "navigation", "structural_drift")},
            "change_kind": r.get("change_kind", "STRUCTURAL_DRIFT" if r["structural_drift"] else "UNKNOWN"),
            "cross_load_variation": r.get("cross_load_variation", False)} for r in records],
        "sections_observed": sorted(sections), "cross_load_patterns": differences,
        "first_observed_at": min((m.workspace.observed_at for m in maps), default=None),
        "last_observed_at": max((m.workspace.observed_at for m in maps), default=None),
        "source": "AscendTMS provider DOM mapping captures", "activation": "CANDIDATE_ONLY",
        "values_included": False, "live_validated": False, "production_writes": False}
