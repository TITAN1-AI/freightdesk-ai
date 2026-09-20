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
        "path": str(ATLAS_PATH.relative_to(ROOT)).replace("\\", "/"),
    }


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
