param(
  [string]$DatabaseUrl = $(if ($env:DATABASE_URL) { $env:DATABASE_URL } else { "mysql+pymysql://root:change-me@127.0.0.1:3307/doctor_care_platform?charset=utf8mb4" }),
  [int]$Patients = 12,
  [int]$Caregivers = 60,
  [int]$Seed = 20260723
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
  throw "Python virtual environment not found: $python"
}

Push-Location $root
try {
  & $python "scripts\seed-recommendation-data.py" `
    --database-url $DatabaseUrl `
    --patients $Patients `
    --caregivers $Caregivers `
    --seed $Seed
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to generate recruitment recommendation data."
  }

  & $python "scripts\train-recruitment-recommender.py" `
    --database-url $DatabaseUrl `
    --output ".local-models\recruitment_recommender.pt" `
    --seed $Seed
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to train the recruitment recommendation model."
  }
} finally {
  Pop-Location
}
