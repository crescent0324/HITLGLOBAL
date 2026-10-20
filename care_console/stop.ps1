$ErrorActionPreference = 'Stop'
$pidFile = Join-Path $PSScriptRoot 'runtime/server.pid'
if (-not (Test-Path -LiteralPath $pidFile)) { throw 'No background PID file. Stop a foreground console with Ctrl+C.' }
$taskPid = [int](Get-Content -LiteralPath $pidFile)
$taskProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$taskPid"
if (-not $taskProcess) { Write-Host 'The background process has already stopped.'; exit }
$expectedRun = Join-Path $PSScriptRoot 'run.py'
if (-not $taskProcess.CommandLine.Contains($expectedRun) -or $taskProcess.Name -ne 'python.exe') {
    throw 'PID belongs to another process; no process was stopped.'
}
$result = Invoke-CimMethod -InputObject $taskProcess -MethodName Terminate
if ($result.ReturnValue -ne 0) { throw ('Windows did not stop the process. Return code: ' + $result.ReturnValue) }
Write-Host 'Care demo stopped. Saved records remain in runtime.'
