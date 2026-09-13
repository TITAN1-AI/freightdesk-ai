# Run manually. Class selection is explicit; the token is never an argument or printed.
param([Parameter(Mandatory=$true)][ValidateSet('agent','tenant')][string]$CredentialClass)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:FREIGHTDESK_RUNTIME_ROOT = 'C:\FreightDeskRuntime'
$secretDirectory = Join-Path $env:FREIGHTDESK_RUNTIME_ROOT 'Secrets'
if ((Get-Item -LiteralPath $env:FREIGHTDESK_RUNTIME_ROOT).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Runtime root must not be a reparse point' }
New-Item -ItemType Directory -Force $secretDirectory | Out-Null
if ((Get-Item -LiteralPath $secretDirectory).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Secret directory must not be a reparse point' }
$secretPath = Join-Path $secretDirectory "carrierview-$CredentialClass-token.dpapi"
if ((Test-Path -LiteralPath $secretPath) -and ((Get-Item -LiteralPath $secretPath).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Secret file must not be a reparse point' }
$carrierViewSecret = Read-Host "Enter the CarrierView $CredentialClass API token (hidden)" -AsSecureString
if ($carrierViewSecret.Length -eq 0) { throw 'Empty token was not saved' }
try {
    $carrierViewSecret | ConvertFrom-SecureString | Set-Content -LiteralPath $secretPath
} finally { $carrierViewSecret.Dispose() }
Write-Output "Encrypted CarrierView $CredentialClass token saved under the approved runtime. No API request was made."
