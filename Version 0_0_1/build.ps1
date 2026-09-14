$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

python -m pip install --upgrade pip
python -m pip install -r agent/requirements.txt

# Regenerate the Windows application icon from the source renderer.
python make_icon.py

# Run the unit test suite before packaging.
pytest

# Build the final single-file Windows executable.
pyinstaller agent/deployment/Agent.spec --clean --noconfirm

$exe = Join-Path $PSScriptRoot "dist\MT5Agent-v0.0.1.exe"
if (-not (Test-Path $exe)) {
    throw "Expected build output was not created: $exe"
}

Write-Host "Build completed: $exe"
