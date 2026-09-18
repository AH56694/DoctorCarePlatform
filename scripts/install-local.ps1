param(
  [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$frontend = Join-Path $root "frontend"

if (-not (Test-Path $pythonExe)) {
  py -3.12 -m venv (Join-Path $root ".venv")
  if ($LASTEXITCODE -ne 0) { throw "Failed to create the Python virtual environment." }
}

& $pythonExe -m pip install --cache-dir (Join-Path $root "temp\pip-cache") `
  -r (Join-Path $root "requirements.txt") `
  -r (Join-Path $root "python-service\requirements.txt") `
  -r (Join-Path $root "requirements-dev.txt")
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }
& $pythonExe -m pip check
if ($LASTEXITCODE -ne 0) { throw "Python dependencies are incompatible." }

if (-not $SkipFrontend) {
  Push-Location $frontend
  try {
    npm ci --cache (Join-Path $root "temp\npm-cache")
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
  } finally {
    Pop-Location
  }
}

Write-Host "Local dependencies are installed."
