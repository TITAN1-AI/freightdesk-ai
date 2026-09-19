"""Manifest and packaged-identity smoke for the portable bridge. Load unpacked is owner-manual."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extensions" / "portable-bridge"
FORBIDDEN = ("nativeMessaging", "connectNative", "eval(", "new Function", "document.cookie",
             "WebSocket(", ".click(", ".submit(", "ASCEND_SAVE", "ASCEND_SET_DRIVER")


def test_portable_manifest_has_no_native_host_and_keeps_write_block():
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert manifest["name"] == "FreightDesk Bridge"
    assert manifest["version"] == "0.1.0"
    assert "nativeMessaging" not in manifest["permissions"]
    assert manifest["permissions"] == ["storage", "alarms", "scripting"]
    assert manifest["host_permissions"][0] == "https://ascendtms.com/*"
    assert "http://127.0.0.1/*" in manifest["host_permissions"]
    assert manifest["content_scripts"][0]["matches"] == ["https://ascendtms.com/*"]
    assert manifest["content_scripts"][0]["world"] == "ISOLATED"
    assert manifest["content_scripts"][0]["all_frames"] is False
    assert "externally_connectable" not in manifest
    assert "web_accessible_resources" not in manifest
    identity = (EXT / "build.js").read_text(encoding="utf-8")
    assert "extension_version: '0.1.0'" in identity
    assert "native_messaging: false" in identity
    assert "live_validated: false" in identity
    assert "production_writes: false" in identity
    sources = "\n".join(path.read_text(encoding="utf-8") for path in EXT.glob("*.js"))
    for token in FORBIDDEN:
        assert token not in sources
    assert "chrome.runtime.connectNative" not in sources
    assert "FreightDeskAscendHost" not in sources


def test_portable_javascript_syntax():
    files = sorted(EXT.glob("*.js"))
    assert files
    for path in files:
        completed = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        assert completed.returncode == 0, path.name + "\n" + completed.stderr
