# Private launcher. Reads only the selected credential; never falls back to the tenant token.
param(
    [Parameter(Mandatory=$true)][string]$ScriptPath,
    [ValidateSet('agent','tenant')][string]$CredentialClass = 'tenant',
    [string]$ElevationReason = 'CarrierView API requires manager/admin credential; Avery employee token is not API-eligible.'
)
$ErrorActionPreference = 'Stop'
if ($CredentialClass -eq 'agent') { throw 'Avery employee credential is unavailable for API execution; tenant is the owner-configured service credential.' }
Set-Location (Split-Path $PSScriptRoot -Parent)
$projectRoot = (Get-Location).Path
$resolvedScript = (Resolve-Path -LiteralPath $ScriptPath).Path
if (-not $resolvedScript.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetExtension($resolvedScript) -ne '.py') {
    throw 'Python script must be inside this project'
}
if ($CredentialClass -eq 'tenant' -and [string]::IsNullOrWhiteSpace($ElevationReason)) { throw 'Tenant token use requires an explicit elevation reason' }
$env:FREIGHTDESK_RUNTIME_ROOT = 'C:\FreightDeskRuntime'
$secretDirectory = Join-Path $env:FREIGHTDESK_RUNTIME_ROOT 'Secrets'
$secretPath = Join-Path $secretDirectory "carrierview-$CredentialClass-token.dpapi"
foreach ($checkedPath in @($env:FREIGHTDESK_RUNTIME_ROOT, $secretDirectory, $secretPath)) {
    if ((Get-Item -LiteralPath $checkedPath).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Runtime credentials must not follow reparse points' }
}
$tokenVariable = "CARRIERVIEW_$($CredentialClass.ToUpperInvariant())_API_TOKEN"
$otherVariable = if ($CredentialClass -eq 'agent') { 'CARRIERVIEW_TENANT_API_TOKEN' } else { 'CARRIERVIEW_AGENT_API_TOKEN' }
$previousCarrierViewToken = [Environment]::GetEnvironmentVariable($tokenVariable, 'Process')
$previousOtherToken = [Environment]::GetEnvironmentVariable($otherVariable, 'Process')
$previousClass = $env:CARRIERVIEW_CREDENTIAL_CLASS
$previousReason = $env:CARRIERVIEW_ELEVATION_REASON
try {
    # Set-Content adds a trailing newline; DPAPI text decoding requires the trimmed encoding.
    $carrierViewEncrypted = (Get-Content -Raw -LiteralPath $secretPath).Trim()
    $carrierViewSecure = ConvertTo-SecureString -String $carrierViewEncrypted
} catch {
    throw 'Selected CarrierView credential could not be decrypted. No API request was made.'
} finally {
    $carrierViewEncrypted = $null
}
$carrierViewCredential = New-Object System.Net.NetworkCredential('', $carrierViewSecure)
try {
    [Environment]::SetEnvironmentVariable($tokenVariable, $carrierViewCredential.Password, 'Process')
    [Environment]::SetEnvironmentVariable($otherVariable, $null, 'Process')
    $env:CARRIERVIEW_CREDENTIAL_CLASS = $CredentialClass
    $env:CARRIERVIEW_ELEVATION_REASON = $ElevationReason
    & '.tools/python/python.exe' $resolvedScript
    if ($LASTEXITCODE -ne 0) { throw 'CarrierView command failed; no credential output was captured' }
} finally {
    [Environment]::SetEnvironmentVariable($tokenVariable, $previousCarrierViewToken, 'Process')
    [Environment]::SetEnvironmentVariable($otherVariable, $previousOtherToken, 'Process')
    $env:CARRIERVIEW_CREDENTIAL_CLASS = $previousClass
    $env:CARRIERVIEW_ELEVATION_REASON = $previousReason
    $carrierViewSecure.Dispose()
    $carrierViewCredential = $null
}
