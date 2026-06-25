$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { Write-Error ".venv가 없습니다. setup_windows.ps1을 먼저 실행하세요."; exit 1 }
& $Python -m streamlit run (Join-Path $Root "app.py")

