$ErrorActionPreference = "SilentlyContinue"

$ports = @(5173, 8000, 8300)
$processIds = Get-NetTCPConnection -LocalPort $ports |
  Where-Object { $_.State -eq "Listen" -and $_.OwningProcess -gt 0 } |
  Select-Object -ExpandProperty OwningProcess -Unique

foreach ($processId in $processIds) {
  Stop-Process -Id $processId -Force
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root
try {
  docker compose stop redis minio mysql
} finally {
  Pop-Location
}

Write-Host "Stopped local app ports 5173, 8000, 8300 and Docker infra redis/minio/mysql."
Write-Host "Logs remain in: $(Join-Path $root '.local-logs')"
