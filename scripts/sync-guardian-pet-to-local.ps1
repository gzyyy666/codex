[CmdletBinding(SupportsShouldProcess)]
param(
  [string]$SourceRoot,
  [string]$TargetRoot = 'C:\Users\26087\Documents\Codex\2026-06-16\vs-code-ai\work\fitness_tracker_app',
  [switch]$SkipBackup
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $SourceRoot) {
  $SourceRoot = Join-Path $repoRoot 'projects\fitness-ledger'
}
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$TargetRoot = [IO.Path]::GetFullPath($TargetRoot)
if ($SourceRoot -eq $TargetRoot) { throw 'Guardian Pet sync source and formal target must be different directories.' }

$relativeFiles = @(
  'ledger_commands.py',
  'fitness_ledger_core\shared_view_models.py',
  'web_desktop\backend\server.py',
  'web_desktop\frontend\app.js',
  'web_desktop\frontend\index.html',
  'web_desktop\frontend\guardian-acceptance.html',
  'web_desktop\frontend\final-pass.css',
  'web_desktop\frontend\tools-css3d-panels.js',
  'web_desktop\frontend\motion-lab\guardian\index.html',
  'web_desktop\frontend\motion-lab\guardian\pet-guardian-static.js',
  'web_desktop\frontend\motion-lab\guardian\guardian-business-adapters.js',
  'web_desktop\frontend\motion-lab\guardian\guardian-intent-map.js',
  'web_desktop\frontend\motion-lab\guardian\guardian-presentation-manager.js',
  'web_desktop\frontend\motion-lab\guardian\guardian-shader-deformation.js',
  'web_desktop\frontend\motion-lab\guardian\config\pose-config.json',
  'web_desktop\frontend\motion-lab\guardian\config\node-map.json',
  'web_desktop\frontend\motion-lab\guardian\config\camera-presets.json',
  'web_desktop\frontend\motion-lab\guardian\config\intent-config.json',
  'web_desktop\frontend\motion-lab\guardian\three.core.min.js',
  'web_desktop\frontend\motion-lab\guardian\three.module.min.js',
  'web_desktop\frontend\motion-lab\guardian\GLTFLoader.js',
  'web_desktop\frontend\motion-lab\guardian\OrbitControls.js',
  'web_desktop\frontend\motion-lab\guardian\BufferGeometryUtils.js',
  'tools\guardian_pet_test.py',
  'tools\guardian_pet_js_test.mjs',
  'web_desktop\frontend\motion-lab\guardian\assets\lowpoly\lowpoly-front-standing.glb',
  'web_desktop\frontend\motion-lab\guardian\assets\lowpoly\lowpoly-side-chest.glb',
  'web_desktop\frontend\motion-lab\guardian\assets\lowpoly\lowpoly-front-double-biceps.glb',
  'web_desktop\frontend\motion-lab\guardian\assets\lowpoly\lowpoly-rear-double-biceps.glb',
  'web_desktop\frontend\motion-lab\guardian\assets\lowpoly\lowpoly-rear-lat-spread.glb',
  'web_desktop\frontend\motion-lab\guardian\assets\lowpoly\lowpoly-most-muscular.glb',
  'web_desktop\frontend\motion-lab\guardian\assets\lowpoly\lowpoly-open-hand-crab.glb',
  'web_desktop\frontend\assets\tools-pet\trophy-champion-v2.png'
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
