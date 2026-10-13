param([string]$DataDirectory = 'data', [string]$DestinationDirectory = 'backups/local')
$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$destinationPath = if ([IO.Path]::IsPathRooted($DestinationDirectory)) { [IO.Path]::GetFullPath($DestinationDirectory) } else { [IO.Path]::GetFullPath((Join-Path $projectDirectory $DestinationDirectory)) }
$logPath = Join-Path $destinationPath 'last-run.log'
try {
    # Initialization protects the directory before any log is written.
    & (Join-Path $projectDirectory '.venv/Scripts/python.exe') -c 'import sys; from server.backup import private_directory; private_directory(sys.argv[1])' $destinationPath
    if ($LASTEXITCODE -ne 0) { throw 'Backup folder initialization failed.' }
    & (Join-Path $projectDirectory 'backup-local.ps1') -DataDirectory $DataDirectory -DestinationDirectory $DestinationDirectory *> $logPath
    @{ success = $true; finished_at = [DateTime]::UtcNow.ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $destinationPath 'last-run.json') -Encoding utf8
} catch {
    # Only operator-tool errors; the backup CLI never prints keys or case content.
    if (Test-Path -LiteralPath $destinationPath) {
        $_.Exception.Message | Add-Content -LiteralPath $logPath -Encoding utf8
        @{ success = $false; finished_at = [DateTime]::UtcNow.ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $destinationPath 'last-run.json') -Encoding utf8
    }
    Write-Error 'Scheduled backup failed. Check the protected backup log and original installation.'
    exit 1
}
