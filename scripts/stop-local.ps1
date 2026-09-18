[CmdletBinding(SupportsShouldProcess)]
param([switch]$KeepInfra)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$logsDir = Join-Path $root ".local-logs"
$records = @(Get-ChildItem -LiteralPath $logsDir -Filter '*.process.json' -File -ErrorAction SilentlyContinue)

foreach ($recordFile in $records) {
  $record = Get-Content -LiteralPath $recordFile.FullName -Raw | ConvertFrom-Json
  if ($record.projectRoot -ne $root) { throw "Process record belongs to a different project." }
  $process = Get-Process -Id ([int]$record.processId) -ErrorAction SilentlyContinue
  # A reused process ID must never authorize stopping a different program.
  if ($process -and [string]$process.StartTime.ToUniversalTime().Ticks -eq $record.startTicks) {
    if (-not $PSCmdlet.ShouldProcess($record.service, "Stop recorded project process and its children")) { continue }
    taskkill /PID $process.Id /T /F
    if ($LASTEXITCODE -ne 0) { throw "Failed to stop $($record.service); process record retained." }
  }
  if ($PSCmdlet.ShouldProcess($recordFile.Name, "Remove finished process record")) {
    Remove-Item -LiteralPath $recordFile.FullName
  }
}

if (-not $KeepInfra -and $PSCmdlet.ShouldProcess("Project Redis, MinIO and MySQL", "Stop Docker infrastructure")) {
  Push-Location $root
  try {
    docker compose stop redis minio mysql
    if ($LASTEXITCODE -ne 0) { throw "Failed to stop Docker infrastructure." }
  } finally {
    Pop-Location
  }
}

Write-Host "Processed recorded project services. Logs remain in: $logsDir"
