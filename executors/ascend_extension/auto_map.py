"""Provider-reviewed, exact-workspace section traversal. No arbitrary selector or script interface."""

import json

from executors.ascend_extension.workspace_contracts import AscendProviderMap, SCOPE, VerifiedSectionNavigation


def approve_navigation(access, session_id, sections, *, owner_authorized=False):
    access._owner(owner_authorized)
    if not sections or len(sections) > 8 or len(set(sections)) != len(sections) or any(s not in SCOPE["sections"] for s in sections):
        raise PermissionError("NAVIGATION_CONTRACT_UNVERIFIED")
    with access.database() as db:
        records = [json.loads(r[0]) for r in db.execute("SELECT body FROM runtime_provider_maps WHERE json_extract(body,'$.session_id')=? ORDER BY id", (session_id,))]
        verified = []
        for section in sections:
            eligible = []
            for record in records:
                m = AscendProviderMap.model_validate(record["map"])
                candidates = [c for c in m.workspace.navigation_candidates if c.section == section]
                if (m.section.section == section and m.section.section_signal == "SELECTED_CONTROL" and len(candidates) == 1
                    and record["navigation"] == "DYNAMIC_SECTION_CHANGE"):
                    eligible.append((record, m, candidates[0]))
            if not eligible:
                raise PermissionError("NAVIGATION_CONTRACT_UNVERIFIED")
            record, m, candidate = eligible[-1]
            contract = VerifiedSectionNavigation(candidate=candidate, classification="READ_ONLY_NAVIGATION", confidence="VERIFIED",
                workspace_fingerprint=m.workspace.shell_fingerprint, evidence_map_version=record["provider_map_version"],
                review_source="OWNER_REVIEWED_PROVIDER_NAVIGATION")
            verified.append(contract)
        for contract in verified:
            db.execute("INSERT INTO runtime_navigation_contracts(body) VALUES (?)", (json.dumps(contract.model_dump()),))
    return {"state": "READ_ONLY_NAVIGATION_REVIEWED", "sections": sections, "operational_fields_activated": False, "production_writes": False}


def plan_auto_map(db, state, raw):
    m = AscendProviderMap.model_validate(raw)
    contracts = {}
    for row in db.execute("SELECT body FROM runtime_navigation_contracts ORDER BY id"):
        c = VerifiedSectionNavigation.model_validate_json(row[0])
        if c.workspace_fingerprint == m.workspace.shell_fingerprint:
            contracts[c.candidate.section] = c
    observed = {c.section: c.fingerprint for c in m.workspace.navigation_candidates}
    if m.section.section not in contracts or not 2 <= len(contracts) <= 8:
        raise PermissionError("NAVIGATION_CONTRACT_UNVERIFIED")
    if any(observed.get(name) != c.candidate.fingerprint for name, c in contracts.items()):
        raise PermissionError("NAVIGATION_CONTROL_CHANGED")
    sections = [name for name in SCOPE["sections"] if name in contracts and name != m.section.section]
    sections.append(m.section.section)  # Exact validated return control is required before the first transition.
    state["auto_plan"] = {"load_id": m.workspace.load_id, "start_section": m.section.section,
        "current_section": m.section.section, "contracts": [contracts[s].model_dump() for s in sections],
        "visited": [m.section.section], "started_at": m.workspace.observed_at, "workspace_fingerprint": m.workspace.shell_fingerprint}


def accept_transition(db, state, lease, pending, raw, now):
    m = AscendProviderMap.model_validate(raw)
    plan = state.get("auto_plan")
    if not plan or not plan["contracts"]:
        raise PermissionError("NAVIGATION_CONTRACT_UNVERIFIED")
    target = plan["contracts"][0]
    if (m.workspace.load_id != plan["load_id"] or m.workspace.shell_fingerprint != plan["workspace_fingerprint"]
        or m.section.section != target["candidate"]["section"] or pending["command"]["navigation"] != target):
        raise PermissionError("WORKSPACE_CHANGED")
    plan["contracts"].pop(0)
    plan["visited"].append(m.section.section)
    plan["current_section"] = m.section.section
    if not plan["contracts"]:
        if m.section.section != plan["start_section"]:
            raise PermissionError("AUTO_MAP_SECTION_UNVERIFIED")
        receipt = {"session_id": lease["mapping"]["session_id"], "load_id": plan["load_id"],
            "sections": plan["visited"], "starting_section": plan["start_section"], "returned_to_start": True,
            "started_at": plan["started_at"], "completed_at": now, "source": "provider DOM verified section receipts",
            "metadata_only": True, "production_writes": False}
        db.execute("INSERT INTO runtime_auto_map_cycles(body) VALUES (?)", (json.dumps(receipt),))
        state["auto_last_cycle"] = receipt
        state["auto_plan"] = None


# Fixed navigation vocabulary only. Action hubs and ambiguous sections are never review candidates.
REVIEWABLE_SECTIONS = frozenset({"Load Basics", "Customer Info", "Carrier / Asset Info", "Edit Stops", "Dispatch and Tracking", "Load Documents", "Load Log"})


def navigation_review_candidates(observed):
    m = AscendProviderMap.model_validate(observed)
    counts = {}
    for candidate in m.workspace.navigation_candidates:
        counts[candidate.section] = counts.get(candidate.section, 0) + 1
    return [c.section for c in m.workspace.navigation_candidates if c.section in REVIEWABLE_SECTIONS and counts[c.section] == 1]


def approve_observed_navigation(access, version, sections, *, owner_authorized=False):
    """One explicit review of structurally observed provider controls, including hidden targets.

    Does not claim a successful section traversal or qualify normal AUTO_MAP.
    The existing executor must prove the expected section after every transition.
    """
    access._owner(owner_authorized)
    if type(version) is not int or not 2 <= len(sections) <= 8 or len(set(sections)) != len(sections):
        raise PermissionError("NAVIGATION_CONTRACT_UNVERIFIED")
    with access.database() as db:
        row = db.execute("SELECT body FROM runtime_provider_maps WHERE json_extract(body,'$.provider_map_version')=?", (version,)).fetchone()
        if not row:
            raise PermissionError("NAVIGATION_CONTRACT_UNVERIFIED")
        record = json.loads(row[0])
        m = AscendProviderMap.model_validate(record["map"])
        if m.section.section not in sections or not set(sections) <= set(navigation_review_candidates(m)):
            raise PermissionError("NAVIGATION_CONTRACT_UNVERIFIED")
        for c in m.workspace.navigation_candidates:
            if c.section in sections:
                contract = VerifiedSectionNavigation(candidate=c, classification="READ_ONLY_NAVIGATION", confidence="VERIFIED",
                    workspace_fingerprint=m.workspace.shell_fingerprint, evidence_map_version=version, review_source="OWNER_REVIEWED_PROVIDER_NAVIGATION")
                db.execute("INSERT INTO runtime_navigation_contracts(body) VALUES (?)", (json.dumps(contract.model_dump()),))
    return {"sections": sections, "production_writes": False}
