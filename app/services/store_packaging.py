"""Chrome/Edge store packaging contract for FreightDesk Bridge. Does not submit."""

from __future__ import annotations

import json
from copy import deepcopy
from urllib.parse import urlparse

from app.core.config import ROOT

UNPACKED_MANIFEST = ROOT / "extensions" / "portable-bridge" / "manifest.json"
PACKAGING_CONFIG = ROOT / "config" / "store-packaging-v0.json"
LOCALHOST_HOST_PERMISSIONS = ("http://127.0.0.1/*", "http://localhost/*")
LOCALHOST_CONNECT_TOKENS = ("http://127.0.0.1", "http://localhost")
FORBIDDEN_PERMISSIONS = (
    "nativeMessaging",
    "<all_urls>",
    "debugger",
    "webRequest",
    "webRequestBlocking",
    "cookies",
    "history",
    "tabs",
    "identity",
    "proxy",
    "management",
)
REQUIRED_PERMISSIONS = ("storage", "alarms", "scripting")
ASCEND_HOST = "https://ascendtms.com/*"
REQUIRED_ICON_SIZES = ("16", "32", "48", "128")


def load_packaging_config() -> dict:
    return json.loads(PACKAGING_CONFIG.read_text(encoding="utf-8"))


def load_unpacked_manifest() -> dict:
    return json.loads(UNPACKED_MANIFEST.read_text(encoding="utf-8"))


def validate_cloud_origin(origin: str) -> str:
    if not origin or origin == "UNSET":
        raise ValueError("cloud_origin_unset")
    parsed = urlparse(origin)
    if parsed.scheme != "https":
        raise ValueError("cloud_origin_https_required")
    host = parsed.hostname or ""
    if not host or host in {"localhost", "127.0.0.1"}:
        raise ValueError("cloud_origin_localhost_forbidden")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("cloud_origin_invalid")
    if parsed.path not in {"", "/"}:
        raise ValueError("cloud_origin_invalid")
    authority = host if parsed.port is None else f"{host}:{parsed.port}"
    return f"https://{authority}"


def _csp(manifest: dict) -> str:
    policy = manifest.get("content_security_policy") or {}
    return str(policy.get("extension_pages") or "")


def store_blockers(manifest: dict | None = None, cloud_origin: str | None = None) -> list[dict]:
    """Return why the current unpacked package must not be submitted."""
    package = load_packaging_config()
    source = manifest if manifest is not None else load_unpacked_manifest()
    blockers: list[dict] = []
    permissions = list(source.get("permissions") or [])
    hosts = list(source.get("host_permissions") or [])
    csp = _csp(source)
    icons = source.get("icons") or {}

    if "nativeMessaging" in permissions:
        blockers.append({"code": "native_messaging_forbidden",
                         "detail": "Store package must not use a Windows native host."})
    for name in FORBIDDEN_PERMISSIONS:
        if name in permissions or name in hosts:
            blockers.append({"code": "permission_forbidden", "detail": name})
    for required in REQUIRED_PERMISSIONS:
        if required not in permissions:
            blockers.append({"code": "permission_missing", "detail": required})
    if ASCEND_HOST not in hosts:
        blockers.append({"code": "ascend_host_missing", "detail": ASCEND_HOST})
    for local in LOCALHOST_HOST_PERMISSIONS:
        if local in hosts:
            blockers.append({"code": "localhost_host_permission", "detail": local})
    for token in LOCALHOST_CONNECT_TOKENS:
        if token in csp:
            blockers.append({"code": "localhost_connect_src", "detail": token})
    if source.get("manifest_version") != 3:
        blockers.append({"code": "manifest_not_mv3", "detail": str(source.get("manifest_version"))})
    scripts = (source.get("content_scripts") or [{}])[0]
    if scripts.get("world") != "ISOLATED":
        blockers.append({"code": "content_script_not_isolated", "detail": str(scripts.get("world"))})
    if scripts.get("all_frames") is True:
        blockers.append({"code": "content_script_all_frames", "detail": "must stay main-frame only"})
    if scripts.get("matches") != [ASCEND_HOST]:
        blockers.append({"code": "content_script_matches", "detail": str(scripts.get("matches"))})
    if "externally_connectable" in source:
        blockers.append({"code": "externally_connectable", "detail": "omit for v0 store"})
    if "web_accessible_resources" in source:
        blockers.append({"code": "web_accessible_resources", "detail": "omit unless a documented need exists"})
    for size in REQUIRED_ICON_SIZES:
        if size not in icons:
            blockers.append({"code": "icon_missing", "detail": size})
    pinned = cloud_origin if cloud_origin is not None else package.get("cloud_api_origin")
    try:
        validate_cloud_origin(str(pinned or "UNSET"))
    except ValueError as exc:
        blockers.append({"code": str(exc), "detail": str(pinned)})
    if package.get("privacy_policy_url") in (None, "", "UNSET"):
        blockers.append({"code": "privacy_policy_url_unset",
                         "detail": "Chrome and Edge require a hosted privacy policy URL."})
    return blockers


def store_ready(cloud_origin: str | None = None) -> bool:
    return not store_blockers(cloud_origin=cloud_origin)


def store_manifest_candidate(cloud_origin: str) -> dict:
    """Build a store-oriented overlay. Does not rewrite the unpacked demo manifest."""
    origin = validate_cloud_origin(cloud_origin)
    candidate = deepcopy(load_unpacked_manifest())
    hosts = [host for host in candidate.get("host_permissions") or []
             if host not in LOCALHOST_HOST_PERMISSIONS]
    cloud_host = origin + "/*"
    if cloud_host not in hosts:
        hosts.append(cloud_host)
    candidate["host_permissions"] = hosts
    candidate["content_security_policy"] = {
        "extension_pages": f"script-src 'self'; object-src 'none'; connect-src {origin}"
    }
    if store_blockers(candidate, cloud_origin=origin):
        # Icons and privacy URL remain blockers even on a valid overlay; those are not
        # manifest host/CSP issues. Filter to overlay-owned codes.
        overlay_codes = {
            "native_messaging_forbidden", "permission_forbidden", "permission_missing",
            "ascend_host_missing", "localhost_host_permission", "localhost_connect_src",
            "manifest_not_mv3", "content_script_not_isolated", "content_script_all_frames",
            "content_script_matches", "externally_connectable", "web_accessible_resources",
            "cloud_origin_unset", "cloud_origin_https_required", "cloud_origin_localhost_forbidden",
            "cloud_origin_invalid",
        }
        leftover = [item for item in store_blockers(candidate, cloud_origin=origin)
                    if item["code"] in overlay_codes]
        if leftover:
            raise ValueError(leftover[0]["code"])
    return candidate


def packaging_status() -> dict:
    package = load_packaging_config()
    blockers = store_blockers()
    return {
        "product": package["product"],
        "track": package["track"],
        "status": package["status"],
        "live_validated": False,
        "production_writes": False,
        "native_messaging": False,
        "store_ready": not blockers,
        "submitted": False,
        "cloud_api_origin": package["cloud_api_origin"],
        "privacy_policy_url": package["privacy_policy_url"],
        "blockers": blockers,
        "product_map": package["product_map"],
        "merge_conflict_risk": package["merge_conflict_risk"],
    }
