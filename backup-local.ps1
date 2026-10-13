param(
    [string]$DataDirectory = 'data',
    [string]$DestinationDirectory = 'backups/local',
    [string]$KeyFile = 'backups/keys/master.key'
)
$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$pythonPath = Join-Path $projectDirectory '.venv/Scripts/python.exe'
function Resolve-BackupPath([string]$Value) {
    if ([IO.Path]::IsPathRooted($Value)) { return [IO.Path]::GetFullPath($Value) }
    return [IO.Path]::GetFullPath((Join-Path $projectDirectory $Value))
}
$sourcePath = Resolve-BackupPath $DataDirectory
$destinationPath = Resolve-BackupPath $DestinationDirectory
$keyPath = Resolve-BackupPath $KeyFile
if (!(Test-Path -LiteralPath $pythonPath)) { throw 'Installed Python environment missing.' }
if (!(Test-Path -LiteralPath (Join-Path $sourcePath 'app.db'))) { throw 'Source database missing; start the application first.' }
Push-Location $projectDirectory
try {
    if (!(Test-Path -LiteralPath $keyPath)) {
        # A missing key with existing backups needs recovery, never silent replacement.
        if ((Test-Path -LiteralPath $destinationPath) -and (Get-ChildItem -LiteralPath $destinationPath -Filter '*.spbackup' -File | Select-Object -First 1)) { throw 'Existing backups found but key is missing. Recover the original key.' }
        & $pythonPath -m server.backup init-key --key-file $keyPath
        if ($LASTEXITCODE -ne 0) { throw 'Could not initialize backup key.' }
    }
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ')
    $archivePath = Join-Path $destinationPath ("schimmelpilz-$stamp.spbackup")
    $revision = 'unknown'
    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if ($gitCommand) {
        $foundRevision = (& $gitCommand.Source rev-parse HEAD 2>$null)
        if ($LASTEXITCODE -eq 0 -and $foundRevision) { $revision = $foundRevision }
    }
    & $pythonPath -m server.backup create --data-dir $sourcePath --output $archivePath --key-file $keyPath --revision $revision
    if ($LASTEXITCODE -ne 0) { throw 'Backup failed. No successful backup was reported.' }
    & $pythonPath -m server.backup verify --backup $archivePath --key-file $keyPath --workspace (Join-Path $destinationPath 'verification')
    if ($LASTEXITCODE -ne 0) { throw 'Backup verification failed; keep the source installation.' }
    Write-Output "Encrypted backup verified: $archivePath"
    Write-Output 'Local copy only. Keep an encrypted copy and the recovery key separately outside this computer for protection against host loss. No older backups were deleted.'
}
finally { Pop-Location }
