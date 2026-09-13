param(
    [Parameter(Mandatory=$true)][ValidateSet('Inspect','Reload','FocusAscend')][string]$Action,
    [Parameter(Mandatory=$true)][long]$WindowHandle
)
# Local browser chrome only. Never reads or writes Ascend DOM, fields, storage or traffic.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class X1BrowserWindow {
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int state);
}
'@
try {
    $window = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$WindowHandle)
    $browserProcess = Get-Process -Id $window.Current.ProcessId
    if ($browserProcess.ProcessName -ne 'msedge') { throw 'LOCAL_BROWSER_IDENTITY_UNVERIFIED' }
    $tabCondition = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::TabItem)
    $tabs = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants,$tabCondition)
    $candidates = @()
    foreach ($tab in $tabs) {
        $tabLabel = $tab.Current.Name
        if ($Action -eq 'FocusAscend') {
            if ($tabLabel -match 'Ascend' -and $tabLabel -notmatch 'FreightDesk') { $candidates += $tab }
        } elseif ($tabLabel -match '^Extensions(?:\s|$)|^Extensiones(?:\s|$)') { $candidates += $tab }
    }
    if ($candidates.Count -ne 1) { throw 'LOCAL_BROWSER_TAB_AMBIGUOUS' }
    ($candidates[0].GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)).Select()
    Start-Sleep -Milliseconds 400
    $address = $window.FindFirst([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty,'Address and search bar'))
    $addressValue = ($address.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)).Current.Value.Trim()
    if ($Action -eq 'FocusAscend') {
        if ($addressValue -notmatch '^(https://)?ascendtms\.com(?:/|$)') { throw 'LOCAL_ASCEND_ORIGIN_UNVERIFIED' }
        [void][X1BrowserWindow]::ShowWindow([IntPtr]$WindowHandle,9)
        [void][X1BrowserWindow]::SetForegroundWindow([IntPtr]$WindowHandle)
        Start-Sleep -Milliseconds 200
        $focused = [X1BrowserWindow]::GetForegroundWindow().ToInt64() -eq $WindowHandle
        if (-not $focused) { throw 'LOCAL_FOREGROUND_UNVERIFIED' }
        # Selecting a tab can leave keyboard focus in browser chrome. Move focus from the
        # verified address bar to page content; X1 alone proves document.hasFocus afterward.
        $address.SetFocus()
        if ([X1BrowserWindow]::GetForegroundWindow().ToInt64() -ne $WindowHandle -or
            [System.Windows.Automation.AutomationElement]::FocusedElement.Current.ProcessId -ne $browserProcess.Id -or
            [System.Windows.Automation.AutomationElement]::FocusedElement.Current.Name -ne 'Address and search bar') { throw 'LOCAL_ADDRESS_FOCUS_UNVERIFIED' }
        $browserKeys = New-Object -ComObject WScript.Shell
        $browserKeys.SendKeys('{F6}')
        [pscustomobject]@{action=$Action;origin_verified=$true;foreground_window_verified=$focused;page_focus_requested=$true;provider_dom_read=$false;production_writes=$false}|ConvertTo-Json -Compress
        exit 0
    }
    if ($addressValue -notmatch '^(edge://)?extensions(?:/|\?|$)') { throw 'LOCAL_MANAGER_IDENTITY_UNVERIFIED' }
    $labels = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty,'FreightDesk Ascend X1'))
    if ($labels.Count -ne 1) { throw 'LOCAL_EXTENSION_CARD_AMBIGUOUS' }
    $card = [System.Windows.Automation.TreeWalker]::ControlViewWalker.GetParent($labels.Item(0))
    $nodes = $card.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
    $reload = @(); $pinned = $false; $version = $false
    foreach ($node in $nodes) {
        $label = $node.Current.Name
        if ($label -match 'opckmnldaebecjphbmdmelfflikinpif') { $pinned = $true }
        if ($label -match '0\.6\.2') { $version = $true }
        if ($node.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button -and $label -match '^Reload(?: extension)?$') { $reload += $node }
    }
    if (-not $pinned -or -not $version -or $reload.Count -ne 1) { throw 'LOCAL_EXTENSION_CARD_UNVERIFIED' }
    if ($Action -eq 'Reload') { ($reload[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)).Invoke() }
    [pscustomobject]@{action=$Action;manager_origin_verified=$true;pinned_extension_id_match=$true;card_version='0.6.2';reload_invoked=($Action -eq 'Reload');provider_dom_read=$false;production_writes=$false}|ConvertTo-Json -Compress
} catch {
    $safe = @('LOCAL_BROWSER_IDENTITY_UNVERIFIED','LOCAL_BROWSER_TAB_AMBIGUOUS','LOCAL_ASCEND_ORIGIN_UNVERIFIED','LOCAL_MANAGER_IDENTITY_UNVERIFIED','LOCAL_EXTENSION_CARD_AMBIGUOUS','LOCAL_EXTENSION_CARD_UNVERIFIED','LOCAL_ADDRESS_FOCUS_UNVERIFIED','LOCAL_FOREGROUND_UNVERIFIED')
    $code = if ($_.Exception.Message -in $safe) { $_.Exception.Message } else { 'LOCAL_BROWSER_MAINTENANCE_FAILED' }
    [pscustomobject]@{action=$Action;safe_stop_code=$code;production_writes=$false}|ConvertTo-Json -Compress
    exit 1
}
