param(
    [int]$ApiPort = 8001,
    [int]$WebPort = 4173,
    [string]$DataDirectory = 'data'
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
