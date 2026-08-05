[CmdletBinding(SupportsShouldProcess)]
param(
  [string]$SourceRoot,
  [string]$TargetRoot = 'C:\Users\26087\Documents\fl\nick-pet-handoff\project\web_desktop\frontend',
  [switch]$SkipBackup
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $SourceRoot) {
  $SourceRoot = Join-Path $repoRoot 'projects\fitness-ledger\web_desktop\frontend'
}
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$TargetRoot = [IO.Path]::GetFullPath($TargetRoot)

$relativeFiles = @(
  'app.js',
  'index.html',
  'final-pass.css',
  'tools-css3d-panels.js',
  'motion-lab\guardian\index.html',
  'motion-lab\guardian\pet-guardian-static.js',
  'motion-lab\guardian\pet-guardian.js',
  'motion-lab\guardian\three.module.min.js',
  'motion-lab\guardian\GLTFLoader.js',
  'motion-lab\guardian\OrbitControls.js',
  'motion-lab\guardian\BufferGeometryUtils.js',
  'motion-lab\guardian\assets\lowpoly\lowpoly-front-standing.glb',
  'motion-lab\guardian\assets\lowpoly\lowpoly-side-chest.glb',
  'motion-lab\guardian\assets\lowpoly\lowpoly-front-double-biceps.glb',
  'motion-lab\guardian\assets\lowpoly\lowpoly-rear-double-biceps.glb',
  'motion-lab\guardian\assets\lowpoly\lowpoly-rear-lat-spread.glb',
  'motion-lab\guardian\assets\lowpoly\lowpoly-most-muscular.glb',
  'motion-lab\guardian\assets\lowpoly\lowpoly-open-hand-crab.glb'
)

$missing = @($relativeFiles | Where-Object { -not (Test-Path -LiteralPath (Join-Path $SourceRoot $_) -PathType Leaf) })
if ($missing.Count) {
  throw "Guardian Pet sync source is incomplete: $($missing -join ', ')"
}

if (-not (Test-Path -LiteralPath $TargetRoot)) {
  New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null
}

$backupRoot = $null
if (-not $SkipBackup) {
  $backupRoot = Join-Path $TargetRoot ('.guardian-pet-sync-backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
  New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
}

foreach ($relative in $relativeFiles) {
  $source = Join-Path $SourceRoot $relative
  $target = Join-Path $TargetRoot $relative
  $targetDirectory = Split-Path -Parent $target
  if (-not (Test-Path -LiteralPath $targetDirectory)) {
    New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
  }
  if ($backupRoot -and (Test-Path -LiteralPath $target -PathType Leaf)) {
    $backup = Join-Path $backupRoot $relative
    $backupDirectory = Split-Path -Parent $backup
    if (-not (Test-Path -LiteralPath $backupDirectory)) {
      New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
    }
    Copy-Item -LiteralPath $target -Destination $backup -Force
  }
  if ($PSCmdlet.ShouldProcess($target, 'Sync Guardian Pet file')) {
    Copy-Item -LiteralPath $source -Destination $target -Force
  }
}

Write-Output "Guardian Pet synced: $TargetRoot"
if ($backupRoot) { Write-Output "Backup created: $backupRoot" }
Write-Output "Files synced: $($relativeFiles.Count)"
