[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('CaptureId','Register','RebuildLauncher','Uninstall','Pair','Reset')][string]$Action,
    [ValidateSet('Edge','Chrome')][string]$Browser = 'Edge',
    [switch]$OwnerExecuted
)
$ErrorActionPreference = 'Stop'
if (-not $OwnerExecuted) { throw 'Explicit owner execution is required.' }
$sourceRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $sourceRoot '.tools\python\python.exe'
$nativeDir = 'C:\FreightDeskRuntime\Data\booking-logistics\ascend-native'
# Verify each absolute runtime component before creating or removing a named local file.
foreach ($component in @('C:\FreightDeskRuntime','C:\FreightDeskRuntime\Data','C:\FreightDeskRuntime\Data\booking-logistics',$nativeDir)) {
    if ((Test-Path -LiteralPath $component) -and ((Get-Item -LiteralPath $component).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Native runtime reparse point rejected.'
    }
}
if ($Action -eq 'CaptureId') {
    New-Item -ItemType Directory -Path $nativeDir -Force | Out-Null
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true,$false)
    $ownerSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $systemSid = New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')
    foreach ($principal in @($ownerSid,$systemSid)) {
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($principal,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
        $acl.SetAccessRule($rule)
    }
    Set-Acl -LiteralPath $nativeDir -AclObject $acl
}
Push-Location $sourceRoot
function Build-NativeLauncher($manifest) {
    $runtimeDir = [System.Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory()
    $compiler = Join-Path $runtimeDir 'csc.exe'
    if (-not (Test-Path -LiteralPath $compiler)) { throw 'Use Windows PowerShell 5.1 with the .NET Framework C# compiler.' }
    $code = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'native_host_launcher.cs') -Raw).Replace('__PYTHON__',$pythonPath.Replace('"','""')).Replace('__SOURCE__',$sourceRoot.Replace('"','""'))
    $buildSource = Join-Path $nativeDir 'launcher.cs'
    [IO.File]::WriteAllText($buildSource,$code)
    & $compiler /nologo /target:exe "/out:$($manifest.path)" $buildSource | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Native launcher build failed; registry unchanged.' }
}
try {
    if ($Action -in @('CaptureId','Pair','Reset')) {
        $verb = @{CaptureId='capture';Pair='pair';Reset='reset'}[$Action]
        & $pythonPath -B -m scripts.ascend_native_setup $verb --owner-executed
        if ($LASTEXITCODE -ne 0) { throw 'Native setup failed; no raw details printed.' }
        return
    }
    $manifestPath = Join-Path $nativeDir 'host-manifest.json'
    foreach ($name in @('host-manifest.json','installation.json','FreightDeskAscendHost.exe','launcher.cs')) {
        $target = Join-Path $nativeDir $name
        if ((Test-Path -LiteralPath $target) -and ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Native runtime file reparse point rejected.'
        }
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $installation = Get-Content -LiteralPath (Join-Path $nativeDir 'installation.json') -Raw | ConvertFrom-Json
    if ($manifest.name -ne 'com.freightdesk.ascend_x1' -or $manifest.type -ne 'stdio' -or
        @($manifest.allowed_origins).Count -ne 1 -or $manifest.allowed_origins[0] -cnotmatch '^chrome-extension://[a-p]{32}/$' -or
        $manifest.allowed_origins[0] -cne ('chrome-extension://' + $installation.extension_id + '/') -or
        $manifest.path -ne (Join-Path $nativeDir 'FreightDeskAscendHost.exe')) { throw 'Native manifest binding invalid.' }
    if ($Action -eq 'RebuildLauncher') {
        Build-NativeLauncher $manifest
        Write-Output 'Native launcher rebuilt at the existing manifest path. Registry and pairing unchanged.'
        return
    }
    $vendor = if ($Browser -eq 'Edge') { 'Microsoft\Edge' } else { 'Google\Chrome' }
    $registryPath = 'Software\' + $vendor + '\NativeMessagingHosts\com.freightdesk.ascend_x1'
    # Only this exact per-user host key is ever modified; no machine-wide or wildcard registration.
    $otherView = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser,[Microsoft.Win32.RegistryView]::Registry64)
    try {
        $otherKey = $otherView.OpenSubKey($registryPath)
        if ($otherKey) {
            $otherKey.Close()
            throw 'Existing registration in the other registry view requires local reconciliation.'
        }
    } finally { $otherView.Close() }
    $hive = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser,[Microsoft.Win32.RegistryView]::Registry32)
    try {
        $existing = $hive.OpenSubKey($registryPath)
        if ($existing) {
            $registered = $existing.GetValue('')
            $existing.Close()
            if ($registered -ne $manifestPath) { throw 'A different native installation owns this registry key.' }
        }
        if ($Action -eq 'Uninstall') {
            & $pythonPath -B -m scripts.ascend_native_setup reset --owner-executed
            if ($LASTEXITCODE -ne 0) { throw 'Pairing reset failed; uninstall stopped.' }
            $hive.DeleteSubKey($registryPath,$false)
            Write-Output 'Owned native registration removed; pairing revoked; audit and request history retained.'
            return
        }
        Build-NativeLauncher $manifest
        $key = $hive.CreateSubKey($registryPath)
        try { $key.SetValue('',$manifestPath,[Microsoft.Win32.RegistryValueKind]::String) } finally { $key.Close() }
        Write-Output 'Native host registered for the selected browser. Pairing and Ascend reads remain separate.'
    } finally { $hive.Close() }
} finally { Pop-Location }
