param(
  [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$frontend = Join-Path $root "frontend"

if (-not (Test-Path $pythonExe)) {
  py -3.12 -m venv (Join-Path $root ".venv")
}

& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $root "requirements.txt")
& $pythonExe -m pip install -r (Join-Path $root "python-service\requirements.txt")

if (-not $SkipFrontend) {
  Push-Location $frontend
  try {
    npm install --cache (Join-Path $root ".npm-cache")
  } finally {
    Pop-Location
  }
}

Write-Host "Local dependencies are installed."
