param([string]$ModelDirectory='data/ocr-models')
$ErrorActionPreference='Stop'
$projectDirectory=$PSScriptRoot
$bundledNode=Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
$nodePath=if(Test-Path -LiteralPath $bundledNode){$bundledNode}else{(Get-Command node -ErrorAction Stop).Source}
$bundledPnpm=Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm.cmd'
$pnpmPath=if(Test-Path -LiteralPath $bundledPnpm){$bundledPnpm}else{(Get-Command pnpm -ErrorAction Stop).Source}
$env:PATH=(Split-Path $nodePath -Parent)+';'+$env:PATH
$target=if([IO.Path]::IsPathRooted($ModelDirectory)){[IO.Path]::GetFullPath($ModelDirectory)}else{[IO.Path]::GetFullPath((Join-Path $projectDirectory $ModelDirectory))}
& $pnpmPath --dir (Join-Path $projectDirectory 'server/ocr') install --frozen-lockfile --ignore-scripts
if($LASTEXITCODE -ne 0){throw 'OCR runtime installation failed.'}
& $nodePath (Join-Path $projectDirectory 'server/ocr/setup-models.mjs') $target
if($LASTEXITCODE -ne 0){throw 'OCR language-model setup failed.'}
Write-Output 'Local OCR runtime and hash-checked German/English language models are ready.'
