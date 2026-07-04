param(
  [string]$Database = "doctor_care_platform",
  [string]$RootPassword = "change-me"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$schemaPath = Join-Path $root "infra\mysql\doctor_care_platform_schema.sql"

if (-not (Test-Path $schemaPath)) {
  throw "MySQL schema file not found: $schemaPath"
}

Push-Location $root
try {
  cmd /c "docker info >nul 2>nul"
  if ($LASTEXITCODE -ne 0) {
    throw "Docker is not running. Start Docker Desktop, then rerun .\scripts\init-mysql.ps1."
  }

  docker compose up -d mysql
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to start the mysql service with Docker Compose."
  }

  $deadline = (Get-Date).AddSeconds(90)
  $ready = $false
  while ((Get-Date) -lt $deadline) {
    docker compose exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot "-p$RootPassword" --silent *> $null
    if ($LASTEXITCODE -eq 0) {
      $ready = $true
      break
    }
    Start-Sleep -Seconds 3
  }

  if (-not $ready) {
    throw "MySQL did not become ready in time."
  }

  Get-Content -Path $schemaPath -Raw -Encoding UTF8 |
    docker compose exec -T mysql mysql -uroot "-p$RootPassword" --default-character-set=utf8mb4

  if ($LASTEXITCODE -ne 0) {
    throw "Failed to initialize MySQL schema."
  }

  Write-Host "MySQL schema initialized: $Database"
} finally {
  Pop-Location
}
