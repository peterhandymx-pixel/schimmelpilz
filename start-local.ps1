param(
    [ValidateRange(1, 65535)][int]$ApiPort = 8001,
    [ValidateRange(1, 65535)][int]$WebPort = 4173,
    [string]$DataDirectory = 'data',
    [switch]$Worker
)
$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$pythonPath = Join-Path $projectDirectory '.venv/Scripts/python.exe'
$ollamaPath = Join-Path $projectDirectory 'data/ollama-v0.35.1/ollama.exe'
$bundledNode = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
$nodePath = if (Test-Path -LiteralPath $bundledNode) { $bundledNode } else { (Get-Command node -ErrorAction Stop).Source }
if (!(Test-Path -LiteralPath $pythonPath)) { throw 'Python environment missing: install server/requirements.txt into .venv first.' }
if (!(Test-Path -LiteralPath $ollamaPath)) { $ollamaPath = (Get-Command ollama -ErrorAction Stop).Source }
$resolvedData = if ([IO.Path]::IsPathRooted($DataDirectory)) { [IO.Path]::GetFullPath($DataDirectory) } else { [IO.Path]::GetFullPath((Join-Path $projectDirectory $DataDirectory)) }
$logDirectory = Join-Path $resolvedData 'logs'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
function Test-LocalService([string]$Url) {
    try { Invoke-RestMethod -Uri $Url -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}
function Start-LocalService([string]$Program, [string[]]$Arguments, [string]$WorkingDirectory, [string]$LogName) {
    Start-Process -FilePath $Program -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory ($LogName + '-output.log')) -RedirectStandardError (Join-Path $logDirectory ($LogName + '-error.log')) | Out-Null
}
if (!$Worker) {
    # WMI launches outside the calling terminal's process job. The hidden worker
    # supplies the runtime environment before starting the ordinary local services.
    # No scheduled task, new permissions or automatic Windows login startup.
    $startupLog = Join-Path $logDirectory "startup-$WebPort.log"
    $escapedScript = $PSCommandPath.Replace("'", "''")
    $escapedData = $resolvedData.Replace("'", "''")
    $escapedLog = $startupLog.Replace("'", "''")
    $workerCode = "& '$escapedScript' -ApiPort $ApiPort -WebPort $WebPort -DataDirectory '$escapedData' -Worker *> '$escapedLog'"
    $encodedWorker = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($workerCode))
    # Reuse the caller's PowerShell edition and its existing execution policy.
    $runtimePowerShell = Join-Path $PSHOME 'pwsh.exe'
    if (!(Test-Path -LiteralPath $runtimePowerShell)) { $runtimePowerShell = Join-Path $PSHOME 'powershell.exe' }
    $launched = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine = ('"' + $runtimePowerShell + '" -NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand ' + $encodedWorker)
        CurrentDirectory = $projectDirectory
    }
    if ($launched.ReturnValue -ne 0) { throw "Could not start independent local services (Windows status $($launched.ReturnValue))." }
    $deadline = [DateTime]::UtcNow.AddSeconds(25)
    do {
        $ready = (Test-LocalService "http://127.0.0.1:$ApiPort/api/health") -and (Test-LocalService "http://127.0.0.1:$WebPort/api/health")
        if ($ready) {
            Write-Output "Schimmelpilz ready: http://localhost:$WebPort/ | API and sign-in proxy responding | Data: $resolvedData | Logs: $logDirectory"
            return
        }
        Start-Sleep -Milliseconds 300
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Local services did not become ready. Check $startupLog and api-$ApiPort / web-$WebPort logs in $logDirectory."
}
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = Join-Path $projectDirectory 'data/models'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:OLLAMA_MODEL = 'qwen2.5:7b'
if (!(Test-LocalService 'http://127.0.0.1:11434/api/tags')) {
    Start-LocalService $ollamaPath @('serve') $projectDirectory 'ollama'
}
$env:DATA_DIR = $resolvedData
if (!(Test-LocalService "http://127.0.0.1:$ApiPort/api/health")) {
    Start-LocalService $pythonPath @('-m', 'uvicorn', 'server.app:app', '--host', '127.0.0.1', '--port', "$ApiPort") $projectDirectory "api-$ApiPort"
}
$env:SCHIMMELPILZ_API_TARGET = "http://127.0.0.1:$ApiPort"
if (!(Test-LocalService "http://127.0.0.1:$WebPort/")) {
    Start-LocalService $nodePath @('node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', "$WebPort", '--strictPort') (Join-Path $projectDirectory 'landing') "web-$WebPort"
}
Write-Output "Schimmelpilz: http://127.0.0.1:$WebPort/ | Data: $resolvedData | Logs: $logDirectory"
