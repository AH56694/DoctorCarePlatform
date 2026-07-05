param(
  [switch]$SkipInfra,
  [switch]$Visible
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonService = Join-Path $root "python-service"
$frontend = Join-Path $root "frontend"
$logsDir = Join-Path $root ".local-logs"
$localModelPath = Join-Path $pythonService "models\bge-small-zh-v1.5"
$faissPath = Join-Path $pythonService "faiss_index"
$mysqlHost = if ($env:MYSQL_HOST) { $env:MYSQL_HOST } else { "127.0.0.1" }
$mysqlPort = if ($env:MYSQL_PORT) { $env:MYSQL_PORT } else { "3306" }
$mysqlDatabase = if ($env:MYSQL_DATABASE) { $env:MYSQL_DATABASE } else { "doctor_care_platform" }
$mysqlUsername = if ($env:MYSQL_USERNAME) { $env:MYSQL_USERNAME } else { "root" }
$mysqlPassword = if ($env:MYSQL_PASSWORD) { $env:MYSQL_PASSWORD } else { "change-me" }
$mysqlPasswordEscaped = [System.Uri]::EscapeDataString($mysqlPassword)
$llmFallbackProviders = if ($env:LLM_FALLBACK_PROVIDERS) { $env:LLM_FALLBACK_PROVIDERS } else { "ollama,openai_compatible,retrieval" }
$ollamaBaseUrl = if ($env:OLLAMA_BASE_URL) { $env:OLLAMA_BASE_URL } else { "http://127.0.0.1:11434" }
$ollamaModel = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { "qwen2.5:0.5b" }
$localLlmTimeout = if ($env:LOCAL_LLM_TIMEOUT_SECONDS) { $env:LOCAL_LLM_TIMEOUT_SECONDS } else { "45" }
$openaiCompatibleBaseUrl = if ($env:OPENAI_COMPATIBLE_BASE_URL) { $env:OPENAI_COMPATIBLE_BASE_URL } else { "" }
$openaiCompatibleApiKey = if ($env:OPENAI_COMPATIBLE_API_KEY) { $env:OPENAI_COMPATIBLE_API_KEY } else { "" }
$openaiCompatibleModel = if ($env:OPENAI_COMPATIBLE_MODEL) { $env:OPENAI_COMPATIBLE_MODEL } else { "" }

function Assert-PathExists($path, $message) {
  if (-not (Test-Path $path)) {
    throw $message
  }
}

function Stop-PortListeners($ports) {
  $processIds = Get-NetTCPConnection -LocalPort $ports -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq "Listen" -and $_.OwningProcess -gt 0 } |
    Select-Object -ExpandProperty OwningProcess -Unique

  foreach ($processId in $processIds) {
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
  }
}

function Start-DevProcess($title, $workingDirectory, $command, $logPath) {
  $logLiteral = $logPath.Replace("'", "''")
  $wrapped = "`$Host.UI.RawUI.WindowTitle = '$title'; `$ErrorActionPreference = 'Continue'; & { $command } *> '$logLiteral'"
  $windowStyle = if ($Visible) { "Normal" } else { "Hidden" }
  return Start-Process powershell -WorkingDirectory $workingDirectory -WindowStyle $windowStyle -PassThru -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command", $wrapped
  )
}

function Wait-Http($name, $url, $timeoutSeconds, $logPath) {
  $deadline = (Get-Date).AddSeconds($timeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 5
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        Write-Host "$name ready: $url"
        return
      }
    } catch {
      Start-Sleep -Seconds 3
    }
  }

  Write-Host ""
  Write-Host "$name did not become ready in ${timeoutSeconds}s. Recent log:"
  if (Test-Path $logPath) {
    Get-Content -Path $logPath -Tail 80
  } else {
    Write-Host "No log file was created: $logPath"
  }
  throw "$name startup failed. Check $logPath"
}

Assert-PathExists (Join-Path $root ".venv\Scripts\python.exe") "Root Python virtual environment is missing. Create it and install requirements.txt first."
Assert-PathExists (Join-Path $frontend "node_modules") "frontend node_modules is missing. Run npm install in frontend first."

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
Remove-Item -LiteralPath (Join-Path $logsDir "*.log") -Force -ErrorAction SilentlyContinue

Stop-PortListeners @(5173, 8000, 8300)

if (-not $SkipInfra) {
  Push-Location $root
  try {
    docker compose up -d redis minio mysql
    & (Join-Path $PSScriptRoot "init-mysql.ps1") -RootPassword $mysqlPassword
  } finally {
    Pop-Location
  }
}

$ragLog = Join-Path $logsDir "rag-service.log"
$backendLog = Join-Path $logsDir "backend.log"
$frontendLog = Join-Path $logsDir "frontend.log"
$rootPython = Join-Path $root ".venv\Scripts\python.exe"

$ragCommand = @"
`$env:PYTHONIOENCODING='utf-8';
`$env:EMBEDDING_MODEL='local';
`$env:LOCAL_EMBEDDING_MODEL_PATH='$localModelPath';
`$env:USE_MILVUS='false';
`$env:VECTOR_STORE_PERSIST_DIR='$faissPath';
`$env:VECTOR_STORE_COLLECTION_NAME='doctorcare_medical_knowledge';
`$env:REDIS_URL='redis://127.0.0.1:6379/0';
`$env:REDIS_HOST='127.0.0.1';
`$env:REDIS_PORT='6379';
`$env:REDIS_DB='0';
`$env:MYSQL_HOST='$mysqlHost';
`$env:MYSQL_PORT='$mysqlPort';
`$env:MYSQL_DATABASE='$mysqlDatabase';
`$env:MYSQL_USERNAME='$mysqlUsername';
`$env:MYSQL_PASSWORD='$mysqlPassword';
`$env:LLM_FALLBACK_PROVIDERS='$llmFallbackProviders';
`$env:OLLAMA_BASE_URL='$ollamaBaseUrl';
`$env:OLLAMA_MODEL='$ollamaModel';
`$env:LOCAL_LLM_TIMEOUT_SECONDS='$localLlmTimeout';
`$env:OPENAI_COMPATIBLE_BASE_URL='$openaiCompatibleBaseUrl';
`$env:OPENAI_COMPATIBLE_API_KEY='$openaiCompatibleApiKey';
`$env:OPENAI_COMPATIBLE_MODEL='$openaiCompatibleModel';
& '$rootPython' -m uvicorn main:app --reload --host 127.0.0.1 --port 8300
"@

$backendCommand = @"
`$env:PYTHONIOENCODING='utf-8';
`$env:DATABASE_URL='mysql+pymysql://$($mysqlUsername):$($mysqlPasswordEscaped)@$($mysqlHost):$($mysqlPort)/$($mysqlDatabase)?charset=utf8mb4';
`$env:RAG_SERVICE_URL='http://127.0.0.1:8300';
`$env:REDIS_URL='redis://127.0.0.1:6379/0';
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
"@

$pythonServiceModuleCheck = @"
import importlib
modules = [
    "fastapi",
    "langchain_core",
    "langchain_text_splitters",
    "sentence_transformers",
    "faiss",
    "dashscope",
    "docx",
    "pytesseract",
    "mysql.connector",
]
missing = []
for module in modules:
    try:
        importlib.import_module(module)
    except Exception:
        missing.append(module)
if missing:
    raise SystemExit("Missing python-service dependencies: " + ", ".join(missing))
"@

try {
  $pythonServiceModuleCheck | & $rootPython -
} catch {
  Write-Host "python-service dependencies are not installed in the root .venv."
  Write-Host "Run: .\scripts\install-local.ps1"
  throw
}

$frontendCommand = "npm run dev -- --host 127.0.0.1"

$ragProcess = Start-DevProcess "DoctorCare RAG python-service :8300" $pythonService $ragCommand $ragLog
Write-Host "Started RAG service process: $($ragProcess.Id)"
Wait-Http "RAG service" "http://127.0.0.1:8300/health" 240 $ragLog

$backendProcess = Start-DevProcess "DoctorCare backend :8000" $root $backendCommand $backendLog
Write-Host "Started backend process: $($backendProcess.Id)"
Wait-Http "Backend" "http://127.0.0.1:8000/health" 90 $backendLog

$frontendProcess = Start-DevProcess "DoctorCare frontend :5173" $frontend $frontendCommand $frontendLog
Write-Host "Started frontend process: $($frontendProcess.Id)"
Wait-Http "Frontend" "http://127.0.0.1:5173/" 90 $frontendLog

Write-Host ""
Write-Host "Local development services are ready."
Write-Host "Frontend:       http://127.0.0.1:5173"
Write-Host "Backend docs:   http://127.0.0.1:8000/docs"
Write-Host "RAG docs:       http://127.0.0.1:8300/docs"
Write-Host "Logs:           $logsDir"
Write-Host ""
Write-Host "To stop everything: .\scripts\stop-local.ps1"
