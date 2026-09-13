# Portable project-local runtime; no system PATH changes.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$projectRoot = (Get-Location).Path
New-Item -ItemType Directory -Force '.tools', '.tmp', 'secrets', 'data', 'logs', 'screenshots' | Out-Null
$env:TEMP = Join-Path $projectRoot '.tmp'
$env:TMP = $env:TEMP
if (-not (Test-Path -LiteralPath '.tools/python/python.exe')) {
    Invoke-WebRequest 'https://www.python.org/ftp/python/3.13.7/python-3.13.7-embed-amd64.zip' -OutFile '.tools/python.zip'
    Expand-Archive -LiteralPath '.tools/python.zip' -DestinationPath '.tools/python' -Force
}
@('python313.zip', '.', $projectRoot, 'Lib\site-packages', 'import site') |
    Set-Content '.tools/python/python313._pth'
& '.tools/python/python.exe' -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
    Invoke-WebRequest 'https://bootstrap.pypa.io/get-pip.py' -OutFile '.tools/get-pip.py'
    & '.tools/python/python.exe' '.tools/get-pip.py' --no-cache-dir --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed' }
}
& '.tools/python/python.exe' -m pip install --no-cache-dir --disable-pip-version-check -r 'requirements.lock'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
Write-Output 'FreightDesk runtime is ready. Run scripts/start.ps1'
