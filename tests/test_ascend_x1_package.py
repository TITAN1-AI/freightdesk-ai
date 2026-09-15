"""Unpacked X1 package identity. No browser, native host, lease or vendor action."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extensions" / "ascend-x1"


def test_unpacked_package_is_complete_v1_only_and_isolated():
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert manifest["version"] == "0.6.2"
    assert "webbridge-v2" not in json.dumps(manifest)
    assert manifest["background"]["service_worker"] == "background.js"
    for name in ("icon16.png", "icon32.png", "icon48.png", "icon128.png"):
        assert (EXT / "icons" / name).stat().st_size > 32
    for script in (
        ROOT / "scripts" / "check-ascend-x1-package.js",
        ROOT / "scripts" / "check-ascend-extension.js",
        ROOT / "scripts" / "check-ascend-native.js",
    ):
        result = subprocess.run(
            ["node", str(script)], cwd=ROOT, capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, result.stdout + result.stderr
