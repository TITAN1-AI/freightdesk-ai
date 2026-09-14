"""Exercise the actual pure PowerShell browser-selection rules without browser access."""
import json
import subprocess
from pathlib import Path


def test_browser_selection_and_exact_origin():
    script = Path(__file__).resolve().parents[1] / 'scripts/x1_browser_selection.ps1'
    source = ". '" + str(script).replace("'", "''") + "'\n" + r'''
$answers = @()
foreach ($url in @('https://ascendtms.com','ascendtms.com/loads','https://ascendtms.com/loads/900001/stops',
    'http://ascendtms.com','https://ascendtms.com.evil.invalid','https://ascendtms.com@evil.invalid',
    'https://evil.invalid/ascendtms.com','https://ascendtms.com:8443','https://user@ascendtms.com')) {
    $answers += (Test-X1AscendOrigin $url)
}
$tabs = @(@{selected=$true;title_candidate=$false},@{selected=$false;title_candidate=$true})
$answers += (Get-X1AscendTabIndex $tabs $true)
$answers += (Get-X1AscendTabIndex $tabs $false)
try { Get-X1AscendTabIndex @(@{selected=$false;title_candidate=$false}) $true; $answers += 'BAD' }
catch { $answers += $_.Exception.Message }
try { Get-X1AscendTabIndex @(@{selected=$true},@{selected=$true}) $true; $answers += 'BAD' }
catch { $answers += $_.Exception.Message }
$answers | ConvertTo-Json -Compress
'''
    result = subprocess.run(['pwsh.exe', '-NoProfile', '-NonInteractive', '-Command', source],
                            capture_output=True, text=True, timeout=20, check=True)
    assert json.loads(result.stdout) == [True, True, True, False, False, False, False, False, False,
                                       0, 1, 'LOCAL_BROWSER_TAB_AMBIGUOUS', 'LOCAL_BROWSER_TAB_AMBIGUOUS']
