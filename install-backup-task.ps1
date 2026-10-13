param([string]$DataDirectory = 'data', [string]$DestinationDirectory = 'backups/local')
$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$sourcePath = if ([IO.Path]::IsPathRooted($DataDirectory)) { [IO.Path]::GetFullPath($DataDirectory) } else { [IO.Path]::GetFullPath((Join-Path $projectDirectory $DataDirectory)) }
$destinationPath = if ([IO.Path]::IsPathRooted($DestinationDirectory)) { [IO.Path]::GetFullPath($DestinationDirectory) } else { [IO.Path]::GetFullPath((Join-Path $projectDirectory $DestinationDirectory)) }
$taskIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$identifier = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($sourcePath.ToLowerInvariant()))).Substring(0,12)
$taskName = "Schimmelpilz-Backup-$identifier"
$scriptPath = Join-Path $projectDirectory 'backup-task.ps1'
$runtimePowerShell = Join-Path $PSHOME 'pwsh.exe'
if (!(Test-Path -LiteralPath $runtimePowerShell)) { $runtimePowerShell = Join-Path $PSHOME 'powershell.exe' }
foreach ($argument in @($scriptPath,$sourcePath,$destinationPath)) { if ($argument.Contains('"')) { throw 'Quoted paths are not supported.' } }
$arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -File "' + $scriptPath + '" -DataDirectory "' + $sourcePath + '" -DestinationDirectory "' + $destinationPath + '"'
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing -and ($existing.Actions.Execute -ne $runtimePowerShell -or $existing.Actions.Arguments -ne $arguments)) { throw 'A different task already uses this name; no replacement made.' }
$action = New-ScheduledTaskAction -Execute $runtimePowerShell -Argument $arguments -WorkingDirectory $projectDirectory
$triggers = @((New-ScheduledTaskTrigger -Daily -At '03:00'), (New-ScheduledTaskTrigger -AtLogOn -User $taskIdentity))
$principal = New-ScheduledTaskPrincipal -UserId $taskIdentity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Principal $principal -Settings $settings -Description 'Private encrypted Schimmelpilz backup. Daily and at sign-in; only while this Windows account is signed in. No cloud upload or automatic deletion.' -Force | Out-Null
Write-Output "Backup task installed: $taskName (daily and at Windows sign-in, limited current-user permissions)."
