$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
try {
    if (-not (Test-Path $Python)) { python -m venv (Join-Path $Root ".venv") }
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -r (Join-Path $Root "requirements.txt")
} catch {
    Write-Error "설치 실패: $($_.Exception.Message)"
    exit 1
}

