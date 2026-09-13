$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:FREIGHTDESK_RUNTIME_ROOT = 'C:\FreightDeskRuntime'
& '.tools/python/python.exe' 'run.py'
