$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

python -m pip install --upgrade pip
python -m pip install -r agent/requirements.txt

pytest
pyinstaller agent/deployment/Agent.spec --clean --noconfirm

Write-Host "Build completed: $PSScriptRoot\dist\Agent.exe"
