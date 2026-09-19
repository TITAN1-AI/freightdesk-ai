$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:FREIGHTDESK_RUNTIME_ROOT = 'C:\FreightDeskRuntime'
$env:PYTHONDONTWRITEBYTECODE = '1'
$testRoot = & '.tools/python/python.exe' -c "from app.core.runtime import RuntimePaths; print(RuntimePaths.from_environment().path('Data', 'TestRuns', 'pytest'))"
if ($LASTEXITCODE -ne 0) { throw 'Test runtime path validation failed' }
$env:TEMP = Split-Path $testRoot -Parent
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
$env:TMP = $env:TEMP
& '.tools/python/python.exe' -m pytest "--basetemp=$testRoot"
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
& '.tools/python/python.exe' -m ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Lint failed' }
node scripts/check-live-view.js
if ($LASTEXITCODE -ne 0) { throw 'Live-view rendering checks failed' }
node --check app/dashboard/mail.js
if ($LASTEXITCODE -ne 0) { throw 'Mail JS syntax failed' }
node scripts/check-mail-view.js
if ($LASTEXITCODE -ne 0) { throw 'Mail-view rendering checks failed' }
node --check app/dashboard/ascend.js
if ($LASTEXITCODE -ne 0) { throw 'Ascend JS syntax failed' }
node --check app/dashboard/portable-facade.js
if ($LASTEXITCODE -ne 0) { throw 'Portable facade JS syntax failed' }
node scripts/check-ascend-view.js
if ($LASTEXITCODE -ne 0) { throw 'Ascend-view rendering checks failed' }
Get-ChildItem extensions/portable-bridge/*.js | ForEach-Object {
  node --check $_.FullName
  if ($LASTEXITCODE -ne 0) { throw "Portable bridge JS syntax failed: $($_.Name)" }
}
