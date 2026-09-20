"""Portable Bridge atlas bindings. CANDIDATE selectors, not LIVE_VALIDATED."""

from __future__ import annotations

import json
from functools import lru_cache

from app.core.config import ROOT

ATLAS_PATH = ROOT / "extensions" / "portable-bridge" / "atlas.json"
CAPABILITY_PATH = ROOT / "config" / "ascend-bridge-capabilities.json"
PRIVATE_NOTE_SELECTOR = "textarea#scratch"
PUBLIC_NOTE_SELECTOR = "#notes"
WHOLE_FORM_SAVE = "WHOLE_FORM_SAVE"
REQUIRED_WRITE_STATUSES = (
    "Active",
    "Available",
    "Assigned",
    "Booked",
    "Dispatched",
    "In Transit",
    "Delivered",
    "Completed",
    "To Be Billed",
)


@lru_cache(maxsize=1)
def load_atlas() -> dict:
    return json.loads(ATLAS_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_capabilities() -> dict:
    return json.loads(CAPABILITY_PATH.read_text(encoding="utf-8"))


def atlas_field(canonical: str) -> dict:
    fields = load_atlas().get("fields") or {}
    if canonical not in fields:
        raise KeyError(canonical)
    return fields[canonical]


def atlas_summary() -> dict:
    atlas = load_atlas()
    fields = atlas.get("fields") or {}
    return {
        "version": atlas.get("version"),
        "origin": atlas.get("origin"),
        "section": atlas.get("section"),
        "provenance": atlas.get("provenance"),
        "live_validated": False,
        "production_writes": False,
        "values_included": False,
        "write_default": atlas.get("write_default"),
        "private_note_selector": PRIVATE_NOTE_SELECTOR,
        "public_note_selector": PUBLIC_NOTE_SELECTOR,
        "commit_kind": WHOLE_FORM_SAVE,
        "field_names": list(fields),
        "status_catalog": list(status_catalog()),
        "path": str(ATLAS_PATH.relative_to(ROOT)).replace("\\", "/"),
    }


def status_catalog() -> tuple[str, ...]:
    raw = load_atlas().get("status_catalog")
    if not isinstance(raw, list) or not raw:
        raise ValueError("atlas_status_catalog_missing")
    values: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            raise ValueError("atlas_status_catalog_invalid")
        text = " ".join(item.split())
        if not text or text == "UNKNOWN" or text in seen:
            raise ValueError("atlas_status_catalog_invalid")
        seen.add(text)
        values.append(text)
    if any(required not in seen for required in REQUIRED_WRITE_STATUSES):
        raise ValueError("atlas_status_catalog_incomplete")
    return tuple(values)


def write_statuses() -> frozenset[str]:
    return frozenset(status_catalog())


def harvest_load_statuses() -> frozenset[str]:
    return frozenset({*status_catalog(), "UNKNOWN"})


def require_atlas_bindings() -> None:
    atlas = load_atlas()
    private = atlas_field("private_notes")
    public = atlas_field("public_notes")
    if private.get("selector") != PRIVATE_NOTE_SELECTOR or private.get("id") != "scratch":
        raise ValueError("atlas_private_note_unbound")
    if private.get("write_method") != WHOLE_FORM_SAVE:
        raise ValueError("atlas_whole_form_save_unbound")
    if public.get("selector") != PUBLIC_NOTE_SELECTOR or public.get("policy") != "FORBIDDEN":
        raise ValueError("atlas_public_note_not_forbidden")
    if atlas.get("section") != "Load Basics":
        raise ValueError("atlas_section_not_load_basics")
    if atlas.get("live_validated") or atlas.get("production_writes"):
        raise ValueError("atlas_live_claim_forbidden")
    catalog = status_catalog()
    status = atlas_field("load_status")
    if list(status.get("allowed_values") or []) != list(catalog):
        raise ValueError("atlas_status_allowed_values_mismatch")
    if status.get("write_method") != WHOLE_FORM_SAVE:
        raise ValueError("atlas_status_whole_form_unbound")
    if status.get("policy") != "APPROVAL_REQUIRED":
        raise ValueError("atlas_status_policy_unbound")
    capabilities = load_capabilities()
    write_status = (capabilities.get("capabilities") or {}).get("write_status") or {}
    if list(write_status.get("allowed_statuses") or []) != list(catalog):
        raise ValueError("capability_status_catalog_mismatch")
    if write_status.get("policy") != "APPROVAL_REQUIRED":
        raise ValueError("capability_status_policy_unbound")
