# Stops the local API (uvicorn), then starts it again with the current .env.
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*uvicorn*server.app:app*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 2
& (Join-Path $PSScriptRoot 'start-local.ps1')
