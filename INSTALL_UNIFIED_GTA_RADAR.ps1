# GTA Radar safe installer — keeps all existing databases and outputs in Desktop/new data.
# Run from PowerShell: powershell -NoProfile -ExecutionPolicy Bypass -File .\INSTALL_UNIFIED_GTA_RADAR.ps1
$ErrorActionPreference = 'Stop'
$repo = 'https://github.com/sandeep89shaily-coder/gta-commercial-radar.git'
$workspaceCandidates = @(
  (Join-Path $env:USERPROFILE 'Desktop\new data'),
  (Join-Path $env:USERPROFILE 'OneDrive\Desktop\new data'),
  (Join-Path $env:USERPROFILE 'OneDrive - Personal\Desktop\new data')
)
$workspace = $workspaceCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Container } | Select-Object -First 1
if (-not $workspace) { throw 'Existing Desktop/new data workspace not found. No data changed.' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required; no files changed.' }
$code = Join-Path $workspace 'GTA_RADAR_UNIFIED_CODE'
if (Test-Path $code) {
  if (-not (Test-Path (Join-Path $code '.git'))) { throw "Refusing to overwrite existing non-git folder: $code" }
  $origin = (& git -C $code remote get-url origin).Trim()
  if ($LASTEXITCODE -ne 0 -or $origin -notmatch 'sandeep89shaily-coder/gta-commercial-radar(\.git)?$') {
    throw "Unexpected Git origin in $code; no changes made"
  }
  $dirty = & git -C $code status --porcelain
  if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'Local code has modifications or untracked files. Refusing destructive update.' }
  & git -C $code pull --ff-only origin main
} else {
  & git clone --branch main --single-branch $repo $code
}
if ($LASTEXITCODE -ne 0) { throw 'Git update failed. Original data untouched.' }
$python = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' } else { throw 'Python missing.' }
if ($python -eq 'py') { & py -3 -m pip install -r (Join-Path $code 'requirements.txt') }
else { & python -m pip install -r (Join-Path $code 'requirements.txt') }
if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed; no intelligence run started.' }
Push-Location $code
try {
  if ($python -eq 'py') { & py -3 -m unittest discover -s tests }
  else { & python -m unittest discover -s tests }
  if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed; no intelligence run started.' }
} finally { Pop-Location }
Write-Host "Code ready: $code"
Write-Host "Existing workspace preserved: $workspace"
Write-Host 'To run after validation:'
Write-Host "  cd `"$code`""
Write-Host "  .\RUN_TOTAL_INTELLIGENCE_TODAY.bat --workspace `"$workspace`""
Write-Host 'No collector or DeepSeek run was started by the installer.'
