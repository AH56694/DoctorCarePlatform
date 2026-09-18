# Exercises lifecycle safety with process APIs mocked; never starts or stops real services.
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$root = Join-Path $project ("temp\process-test-" + [Guid]::NewGuid().ToString('N'))
$logsDir = Join-Path $root '.local-logs'
$scriptDir = Join-Path $root 'scripts'
New-Item -ItemType Directory -Path $logsDir, $scriptDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $project 'scripts\stop-local.ps1') -Destination $scriptDir
$Visible = $false

function Assert-True($condition, $message) {
  if (-not $condition) { throw $message }
}

$parseTokens = $null
$parseErrors = $null
$tree = [Management.Automation.Language.Parser]::ParseFile(
  (Join-Path $project 'scripts\start-local.ps1'), [ref]$parseTokens, [ref]$parseErrors
)
Assert-True ($parseErrors.Count -eq 0) 'Start script must parse.'
foreach ($name in @('Start-DevProcess', 'Assert-PortsAvailable')) {
  $definition = $tree.Find({ param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
  }, $true)
  . ([ScriptBlock]::Create($definition.Extent.Text))
}

$global:DcpProcessTestState = @{}
$global:DcpProcessTestState.startedAt = Get-Date
$global:DcpProcessTestState.killCount = 0
function Start-Process {
  param($FilePath, $WorkingDirectory, $WindowStyle, [switch]$PassThru, $ArgumentList)
  $global:DcpProcessTestState.spawnArgs = $ArgumentList -join ' '
  $global:DcpProcessTestState.inherited = $env:DCP_PROCESS_TEST
  $global:DcpProcessTestState.windowStyleSeen = $WindowStyle
  [pscustomobject]@{ Id = 900001; StartTime = $global:DcpProcessTestState.startedAt }
}
function Get-NetTCPConnection { param($LocalPort, $State, $ErrorAction)
  [pscustomobject]@{ LocalPort = 8000 }
}
function Get-Process { param($Id, $ErrorAction)
  [pscustomobject]@{ Id = $Id; StartTime = $global:DcpProcessTestState.observedStartTime }
}
function taskkill { $global:DcpProcessTestState.killCount++; $global:LASTEXITCODE = 0 }

$prior = $env:DCP_PROCESS_TEST
try {
  $env:DCP_PROCESS_TEST = 'parent-value'
  $sampleSecret = 'sample-''value$()'
  $null = Start-DevProcess 'Test service' $root 'Write-Output ready' (Join-Path $logsDir 'test.log') @{
    DCP_PROCESS_TEST = $sampleSecret
  }
  Assert-True ($global:DcpProcessTestState.inherited -eq $sampleSecret) 'Child must inherit the exact value.'
  Assert-True ($env:DCP_PROCESS_TEST -eq 'parent-value') 'Parent environment must be restored.'
  Assert-True (-not $global:DcpProcessTestState.spawnArgs.Contains($sampleSecret)) 'Secret must not appear in process arguments.'
  Assert-True ($global:DcpProcessTestState.windowStyleSeen -eq 'Hidden') 'Background windows must remain hidden.'
  $recordPath = Join-Path $logsDir '900001.process.json'
  $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
  Assert-True ($record.projectRoot -eq $root) 'Process ownership must be recorded.'

  $blocked = $false
  try { Assert-PortsAvailable @(8000) } catch { $blocked = $true }
  Assert-True $blocked 'Occupied ports must block startup.'

  $stopScript = Join-Path $scriptDir 'stop-local.ps1'
  $global:DcpProcessTestState.observedStartTime = $global:DcpProcessTestState.startedAt.AddSeconds(10)
  & $stopScript -KeepInfra
  Assert-True ($global:DcpProcessTestState.killCount -eq 0) 'A reused process ID must not be killed.'

  $record | ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding UTF8
  $global:DcpProcessTestState.observedStartTime = $global:DcpProcessTestState.startedAt
  & $stopScript -KeepInfra -WhatIf
  Assert-True ($global:DcpProcessTestState.killCount -eq 0) 'Preview must not stop any process.'
  Assert-True (Test-Path -LiteralPath $recordPath) 'Preview must preserve the record.'
  & $stopScript -KeepInfra
  Assert-True ($global:DcpProcessTestState.killCount -eq 1) 'Only a matching recorded process may be stopped.'
  Assert-True (-not (Test-Path -LiteralPath $recordPath)) 'Completed process record must be removed.'
  Write-Output 'Local lifecycle safety checks passed (process APIs mocked).'
} finally {
  [Environment]::SetEnvironmentVariable('DCP_PROCESS_TEST', $prior, 'Process')
  Remove-Variable -Name DcpProcessTestState -Scope Global
}
