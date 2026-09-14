$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python make_icon.py
pytest -q

pyinstaller deployment/Agent.spec --clean --noconfirm

$exe = Join-Path $PSScriptRoot "dist\MT5Agent-v0.0.2.exe"
if (-not (Test-Path $exe)) {
    throw "Expected build output was not created: $exe"
}

Write-Host "Build completed: $exe"
