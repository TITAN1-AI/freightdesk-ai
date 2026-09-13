"""Actual worker/router/content lifecycle with synthetic ports and provider reader only."""

import subprocess


def test_observe_refresh_foreground_replacement_and_signed_wake():
    result = subprocess.run(
        ["node", "scripts/check-x1-observe-lifecycle-review.js"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"result":"PASSED"' in result.stdout
