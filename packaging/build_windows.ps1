$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Create .venv and install Windows dependencies first." }
New-Item -ItemType Directory -Force (Join-Path $Root "packaging\out") | Out-Null
& $Python -m PyInstaller --noconfirm --clean --distpath (Join-Path $Root "packaging\out") --workpath (Join-Path $Root "build\windows") (Join-Path $PSScriptRoot "windows.spec")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$Exe = Join-Path $Root "packaging\out\TimeTrace.exe"
$Hash = (Get-FileHash $Exe -Algorithm SHA256).Hash.ToLower()
"$Hash  TimeTrace.exe" | Set-Content -Encoding ascii (Join-Path $Root "packaging\out\SHA256SUMS")
Write-Host "Built $Exe"