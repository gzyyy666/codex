[CmdletBinding()]
param(
    [string]$SourceRoot = $env:FITNESS_LEDGER_SOURCE_ROOT,
    [string]$MirrorRoot = (Join-Path $PSScriptRoot '..\projects\fitness-ledger'),
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$usage = 'Set FITNESS_LEDGER_SOURCE_ROOT to the formal project root, or pass -SourceRoot <path>.'
if ([string]::IsNullOrWhiteSpace($SourceRoot)) { throw $usage }
$policy = Import-PowerShellDataFile (Join-Path $PSScriptRoot 'fitness-ledger-mirror-allowlist.psd1')
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$MirrorRoot = (Resolve-Path -LiteralPath $MirrorRoot).Path

function Relative-Path([string]$Root, [string]$FullName) {
    return $FullName.Substring($Root.Length + 1).Replace('\', '/')
}

function Is-ExplicitlyExcluded([string]$Relative) {
    $lower = $Relative.ToLowerInvariant()
    # These are prefix exclusions rather than fixed directory names: every
    # QA Edge profile variant is local browser state.
    if ($lower -match '^web_desktop/\.qa-edge') { return $true }
    # This is a tracked, non-sensitive template despite the word "local".
    if ($lower -eq 'cloud_sync/cloud_config.local.json.example') { return $false }
    if ($lower -match '(^|/)(__pycache__|node_modules)(/|$)|\.(pyc|pyo|log|tmp|xlsx)$') { return $true }
    if ($lower -match '(^|/)\.env($|\.)|(^|/).*\.local\.[^/]+$') { return $true }
    foreach ($entry in $policy.ExplicitExclusions) {
        $normalized = $entry.Replace('\', '/').ToLowerInvariant()
        if ($normalized.EndsWith('/')) {
            if ($lower.StartsWith($normalized)) { return $true }
        } elseif ($lower -eq $normalized -or $lower.StartsWith($normalized + '/')) { return $true }
    }
    return $false
}

function Is-Allowed([string]$Relative) {
    if (Is-ExplicitlyExcluded $Relative) { return $false }
    if ($policy.RootFiles -contains $Relative) { return $true }
    $parts = $Relative.Split('/', 2)
    if ($parts.Count -lt 2 -or -not $policy.DirectoryRules.ContainsKey($parts[0])) { return $false }
    $name = [System.IO.Path]::GetFileName($Relative)
    foreach ($suffix in $policy.DirectoryRules[$parts[0]]) {
        if ($name.EndsWith($suffix, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

$sourceFiles = Get-ChildItem -LiteralPath $SourceRoot -File -Recurse -Force
$candidates = @()
$skipped = @()
foreach ($file in $sourceFiles) {
    $relative = Relative-Path $SourceRoot $file.FullName
    if (Is-Allowed $relative) { $candidates += [pscustomobject]@{ Relative = $relative; Source = $file.FullName; Length = $file.Length } }
    else { $skipped += [pscustomobject]@{ Relative = $relative; Reason = if (Is-ExplicitlyExcluded $relative) { 'excluded' } else { 'not-allowlisted' }; Length = $file.Length } }
}

$adds = @(); $updates = @(); $unchanged = @()
foreach ($candidate in $candidates) {
    $destination = Join-Path $MirrorRoot $candidate.Relative.Replace('/', '\')
    if (-not (Test-Path -LiteralPath $destination)) { $adds += $candidate; continue }
    $same = (Get-FileHash -LiteralPath $candidate.Source -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
    if ($same) { $unchanged += $candidate } else { $updates += $candidate }
}

$mirrorOnly = Get-ChildItem -LiteralPath $MirrorRoot -File -Recurse -Force | ForEach-Object {
    $relative = Relative-Path $MirrorRoot $_.FullName
    if (-not ($candidates.Relative -contains $relative)) { [pscustomobject]@{ Relative = $relative; Length = $_.Length } }
}

$patterns = @(
    @{ Name = 'cloud credential value'; Regex = '(?i)(secret(id|key)|accesskey|api[ _-]?key|credential)\s*[:=]\s*["''][^"''\s]{8,}' },
    @{ Name = 'authentication token value'; Regex = '(?i)bearer\s+[a-z0-9._-]{12,}|authorization\s*[:=]\s*["''][^"''\s]{12,}|token\s*[:=]\s*["''][^"''\s]{12,}' },
    @{ Name = 'password value'; Regex = '(?i)password\s*[:=]\s*["''][^"''\s]{8,}' },
    @{ Name = 'private key'; Regex = '-----BEGIN [A-Z ]*PRIVATE KEY-----' },
    @{ Name = 'local absolute path'; Regex = '(?i)[A-Z]:\\Users\\|/Users/|/home/' },
    @{ Name = 'browser session'; Regex = '(?i)cookie|local storage|login state' }
)
$sensitive = @()
foreach ($candidate in $candidates) {
    if ($candidate.Length -gt 2097152) { continue }
    foreach ($pattern in $patterns) {
        $match = Select-String -LiteralPath $candidate.Source -Pattern $pattern.Regex -Quiet -ErrorAction SilentlyContinue
        if ($match) { $sensitive += [pscustomobject]@{ Relative = $candidate.Relative; MatchType = $pattern.Name } }
    }
}

$suspicious = $skipped | Where-Object { $_.Reason -eq 'not-allowlisted' -and $_.Relative -match '(?i)\.(py|pyw|js|css|html|wxml|wxss|json|md)$' }
$large = $candidates | Where-Object { $_.Length -gt $policy.LargeFileBytes }

Write-Output "MODE: $(if ($Apply) { 'APPLY' } else { 'PREVIEW' })"
Write-Output 'ADD'; $adds | Sort-Object Relative | Format-Table Relative,Length -AutoSize
Write-Output 'UPDATE'; $updates | Sort-Object Relative | Format-Table Relative,Length -AutoSize
Write-Output 'UNCHANGED'; $unchanged | Sort-Object Relative | Format-Table Relative,Length -AutoSize
Write-Output 'SKIPPED'; $skipped | Sort-Object Reason,Relative | Format-Table Reason,Relative,Length -AutoSize
Write-Output 'MIRROR_ONLY_PRESERVED'; $mirrorOnly | Sort-Object Relative | Format-Table Relative,Length -AutoSize
Write-Output 'POSSIBLE_DELETIONS: none (this tool never deletes mirror files)'
Write-Output 'SENSITIVE_SCAN'; if ($sensitive) { $sensitive | Sort-Object Relative,MatchType | Format-Table Relative,MatchType -AutoSize } else { 'none' }
Write-Output 'LARGE_CANDIDATES'; if ($large) { $large | Sort-Object Length -Descending | Format-Table Relative,Length -AutoSize } else { 'none' }
Write-Output 'UNLISTED_CODE_OR_DOC_CANDIDATES'; if ($suspicious) { $suspicious | Sort-Object Relative | Format-Table Relative,Length -AutoSize } else { 'none' }

if ($sensitive) { throw 'Sensitive-content matches found. Resolve them before any Apply run.' }
if ($Apply) {
    foreach ($candidate in @($adds) + @($updates)) {
        $destination = Join-Path $MirrorRoot $candidate.Relative.Replace('/', '\')
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
        Copy-Item -LiteralPath $candidate.Source -Destination $destination -Force
    }
}
