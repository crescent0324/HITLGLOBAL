param([switch]$Background)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$runtimeDir = Join-Path $taskRoot 'runtime'
$runFile = Join-Path $taskRoot 'run.py'
$pythonPath = Join-Path $taskRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { $pythonPath = $null }
if (-not $pythonPath) { throw 'Python environment unavailable. See README.md for setup.' }
& $pythonPath -B -c 'import flask, waitress'
if ($LASTEXITCODE -ne 0) { throw 'Missing dependencies. See README.md for setup.' }
$portInUse = $false
$portProbe = New-Object System.Net.Sockets.TcpClient
try { $portProbe.Connect('127.0.0.1', 9465); $portInUse = $true } catch { } finally { $portProbe.Dispose() }
if ($portInUse) { throw 'Port 9465 is in use. Open http://127.0.0.1:9465/ or check the existing process first.' }
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
Write-Host 'Care demo: http://127.0.0.1:9465/ (local only)'
if ($Background) {
    $taskProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-B', ('"' + $runFile + '"')) -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir 'server.out.log') -RedirectStandardError (Join-Path $runtimeDir 'server.err.log')
    Start-Sleep -Milliseconds 900
    $taskProcess.Refresh()
    if ($taskProcess.HasExited) { throw ('Care demo could not start. Check ' + (Join-Path $runtimeDir 'server.err.log')) }
    $taskProcess.Id | Set-Content -LiteralPath (Join-Path $runtimeDir 'server.pid')
    Write-Host ('Started process ' + $taskProcess.Id)
} else {
    Write-Host 'Keep this console open. Ctrl+C stops this demo; thesis prototype is separate.'
    & $pythonPath -B $runFile
}
