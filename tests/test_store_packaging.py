"""Store packaging contract. Unpacked demo is not a Chrome/Edge submission."""

import json
from pathlib import Path

import pytest

from app.services.store_packaging import (
    ASCEND_HOST,
    FORBIDDEN_PERMISSIONS,
    LOCALHOST_HOST_PERMISSIONS,
    REQUIRED_PERMISSIONS,
    load_packaging_config,
    load_unpacked_manifest,
    packaging_status,
    store_blockers,
    store_manifest_candidate,
    store_ready,
    validate_cloud_origin,
)

ROOT = Path(__file__).resolve().parents[1]
CLOUD = "https://cloud.freightdesk.example"


def test_packaging_config_is_not_submitted_and_maps_demo_vs_store():
    package = load_packaging_config()
    assert package["status"] == "DOCUMENTED_NOT_SUBMITTED"
    assert package["live_validated"] is False
    assert package["production_writes"] is False
    assert package["native_messaging"] is False
    assert package["titan_01_required"] is False
    assert package["windows_native_host_required"] is False
    assert package["cloud_api_origin"] == "UNSET"
    assert package["privacy_policy_url"] == "UNSET"
    mapped = package["product_map"]
    assert "Load unpacked" in mapped["demo_only"]
    assert "PLACEHOLDER popup Demo sign-in" in mapped["demo_only"]
    assert any("Chrome Web Store" in item for item in mapped["store_path"])
    assert "Assign and money FORBIDDEN" in mapped["same_in_both"]
    assert package["merge_conflict_risk"]["open_pr"] == 11
    assert "extensions/portable-bridge/harvest.js" in package["merge_conflict_risk"]["do_not_rewrite_here"]


def test_unpacked_manifest_is_blocked_from_store_submit():
    manifest = load_unpacked_manifest()
    assert manifest["manifest_version"] == 3
    assert manifest["version"] == "0.1.12"
    assert "nativeMessaging" not in manifest["permissions"]
    assert manifest["permissions"] == list(REQUIRED_PERMISSIONS)
    for local in LOCALHOST_HOST_PERMISSIONS:
        assert local in manifest["host_permissions"]
    codes = {item["code"] for item in store_blockers()}
    assert "localhost_host_permission" in codes
    assert "localhost_connect_src" in codes
    assert "icon_missing" in codes
    assert "cloud_origin_unset" in codes
    assert "privacy_policy_url_unset" in codes
    assert store_ready() is False
    status = packaging_status()
    assert status["store_ready"] is False
    assert status["submitted"] is False
    assert status["native_messaging"] is False


def test_store_manifest_candidate_strips_localhost_and_pins_https_cloud():
    candidate = store_manifest_candidate(CLOUD)
    assert ASCEND_HOST in candidate["host_permissions"]
    assert CLOUD + "/*" in candidate["host_permissions"]
    for local in LOCALHOST_HOST_PERMISSIONS:
        assert local not in candidate["host_permissions"]
    csp = candidate["content_security_policy"]["extension_pages"]
    assert "http://127.0.0.1" not in csp
    assert "http://localhost" not in csp
    assert "connect-src " + CLOUD in csp
    assert "script-src 'self'" in csp
    assert "nativeMessaging" not in candidate["permissions"]
    for name in FORBIDDEN_PERMISSIONS:
        assert name not in candidate["permissions"]
    assert candidate["content_scripts"][0]["world"] == "ISOLATED"
    assert candidate["content_scripts"][0]["all_frames"] is False
    assert candidate["content_scripts"][0]["matches"] == [ASCEND_HOST]
    unpacked = json.loads((ROOT / "extensions" / "portable-bridge" / "manifest.json").read_text())
    assert "http://127.0.0.1/*" in unpacked["host_permissions"]


def test_cloud_origin_validation_rejects_loopback_and_http():
    assert validate_cloud_origin(CLOUD) == CLOUD
    with pytest.raises(ValueError, match="cloud_origin_unset"):
        validate_cloud_origin("UNSET")
    with pytest.raises(ValueError, match="cloud_origin_https_required"):
        validate_cloud_origin("http://cloud.freightdesk.example")
    with pytest.raises(ValueError, match="cloud_origin_localhost_forbidden"):
        validate_cloud_origin("https://localhost")
    with pytest.raises(ValueError, match="cloud_origin_invalid"):
        validate_cloud_origin("https://cloud.freightdesk.example/v1")


def test_store_handoff_docs_exist():
    docs = ROOT / "docs"
    packaging = (docs / "STORE_PACKAGING_V0.md").read_text(encoding="utf-8")
    oauth = (docs / "CLOUD_LEASE_OAUTH_V0.md").read_text(encoding="utf-8")
    listing = (ROOT / "extensions" / "portable-bridge" / "STORE_LISTING.md").read_text(encoding="utf-8")
    assets = (ROOT / "extensions" / "portable-bridge" / "store" / "README.md").read_text(encoding="utf-8")
    assert "Chrome Web Store" in packaging
    assert "Edge Add-ons" in packaging
    assert "https://ascendtms.com/*" in packaging
    assert "nativeMessaging" in packaging
    assert "PR #11" in packaging
    assert "NOT_CONFIGURED" in oauth
    assert "PLACEHOLDER" in oauth
    assert "mints_session" in oauth
    assert "RFC 8628" in oauth
    assert "STORE_PACKAGING_V0.md" in listing
    assert "store_manifest_candidate" in assets
