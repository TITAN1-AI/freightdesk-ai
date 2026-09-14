# Browser-chrome selection only. Never emits addresses or tab labels.
function Test-X1AscendOrigin([string]$Address) {
    $candidate = $Address.Trim()
    if ($candidate -match '^ascendtms\.com(?:/|$)') { $candidate = 'https://' + $candidate }
    $parsed = $null
    if (-not [Uri]::TryCreate($candidate, [UriKind]::Absolute, [ref]$parsed)) { return $false }
    return $parsed.Scheme -eq 'https' -and $parsed.Host -eq 'ascendtms.com' -and
        $parsed.IsDefaultPort -and $parsed.UserInfo -eq ''
}

function Get-X1AscendTabIndex([object[]]$Facts, [bool]$SelectedOriginVerified) {
    $matches = @()
    for ($i = 0; $i -lt $Facts.Count; $i++) {
        if (($SelectedOriginVerified -and $Facts[$i].selected) -or
            (-not $SelectedOriginVerified -and $Facts[$i].title_candidate)) { $matches += $i }
    }
    if ($matches.Count -ne 1) { throw 'LOCAL_BROWSER_TAB_AMBIGUOUS' }
    return $matches[0]
}
