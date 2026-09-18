param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('validate', 'test', 'build', 'smoke-invalid', 'smoke-unavailable', 'package')]
    [string]$Task,
    [string]$PythonExecutable = 'python',
    [string]$ArtifactName = 'MT5Agent-v0.1.0'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$exePath = Join-Path $repoRoot "dist\$ArtifactName.exe"
$reportRoot = Join-Path $repoRoot 'reports'

function Invoke-Python {
    param([string[]]$Arguments)
    & $PythonExecutable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code ${LASTEXITCODE}: $($Arguments -join ' ')"
    }
}

function Get-BinaryHash {
    if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
        throw "Expected executable does not exist: $exePath"
    }
    return (Get-FileHash -LiteralPath $exePath -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Invoke-Smoke {
    param([string]$Name, [int]$ExpectedExit, [string]$ExpectedErrorPattern)
    $beforeHash = Get-BinaryHash
    $stdout = Join-Path $reportRoot "$Name.stdout.log"
    $stderr = Join-Path $reportRoot "$Name.stderr.log"
    $process = Start-Process -FilePath $exePath -WorkingDirectory $repoRoot `
        -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    try {
        if (-not $process.WaitForExit(60000)) {
            # Only stop the process this smoke test started. Do not touch MT5.
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            throw "$Name exceeded the 60-second limit"
        }
        $process.WaitForExit()
        $actualExit = $process.ExitCode
        if ($actualExit -ne $ExpectedExit) {
            throw "$Name expected exit $ExpectedExit but received $actualExit; see reports/$Name.stderr.log"
        }
        $errorLog = Get-Content -LiteralPath $stderr -Raw
        if ($errorLog -notmatch $ExpectedErrorPattern) {
            throw "$Name exited as expected but did not report the expected application failure"
        }
        if ((Get-BinaryHash) -ne $beforeHash) {
            throw 'Executable changed while smoke testing'
        }
        [ordered]@{
            test = $Name
            executable = "$ArtifactName.exe"
            sha256 = $beforeHash
            expected_exit = $ExpectedExit
            actual_exit = $actualExit
        } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportRoot "$Name.json") -Encoding utf8
        Write-Output "$Name passed: exit $actualExit; SHA256=$beforeHash"
    }
    finally {
        $process.Dispose()
    }
}

Push-Location $repoRoot
try {
    New-Item -ItemType Directory -Path $reportRoot -Force | Out-Null
    switch ($Task) {
        'validate' {
            $historical = @(Get-ChildItem -LiteralPath $repoRoot -Directory | Where-Object { $_.Name -like 'Version *' })
            if ($historical.Count -gt 0) {
                throw 'Historical version directories must not be present in the active tree'
            }
            Invoke-Python -Arguments @('-m', 'compileall', '-q', 'agent', 'main.py')
            Invoke-Python -Arguments @('-c', 'from pathlib import Path; import agent, agent.main, agent.composition, agent.__main__, main; assert Path(agent.__file__).resolve() == Path("agent/__init__.py").resolve(); assert main.run is agent.main.run; print("Active package and both entry points imported successfully")')
        }
        'test' {
            Invoke-Python -Arguments @('-m', 'pytest', '-q', '--durations=20', '--junitxml=reports/pytest.xml')
        }
        'build' {
            Invoke-Python -Arguments @('deployment/make_icon.py')
            Invoke-Python -Arguments @('-m', 'PyInstaller', 'deployment/Agent.spec', '--clean', '--noconfirm')
            Write-Output "Built $exePath; SHA256=$(Get-BinaryHash)"
        }
        'smoke-invalid' {
            $previousPort = [Environment]::GetEnvironmentVariable('MT5_AGENT_HTTP_PORT', 'Process')
            try {
                $env:MT5_AGENT_HTTP_PORT = 'invalid'
                Invoke-Smoke -Name 'invalid-configuration' -ExpectedExit 2 -ExpectedErrorPattern 'Invalid startup configuration: MT5_AGENT_HTTP_PORT must be an integer'
            }
            finally {
                [Environment]::SetEnvironmentVariable('MT5_AGENT_HTTP_PORT', $previousPort, 'Process')
            }
        }
        'smoke-unavailable' {
            if ($env:MT5_TERMINAL_UNAVAILABLE_CONFIRMED -ne 'true') {
                throw 'Use an isolated VM with no accessible MT5 terminal, then explicitly set MT5_TERMINAL_UNAVAILABLE_CONFIRMED=true'
            }

            $names = @('MT5_AGENT_HTTP_HOST', 'MT5_AGENT_HTTP_PORT', 'MT5_AGENT_HTTP_MAX_REQUEST_BYTES')
            $previousValues = @{}

            try {
                foreach ($name in $names) {
                    $previousValues[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
                }

                $env:MT5_AGENT_HTTP_HOST = '127.0.0.1'
                $env:MT5_AGENT_HTTP_PORT = '18080'
                $env:MT5_AGENT_HTTP_MAX_REQUEST_BYTES = '1048576'

                Invoke-Smoke -Name 'terminal-unavailable' -ExpectedExit 1 -ExpectedErrorPattern '\(agent_start_failed\)'
            }
            finally {
                foreach ($name in $names) {
                    [Environment]::SetEnvironmentVariable($name, $previousValues[$name], 'Process')
                }
            }
        }
        'package' {
            $binaryHash = Get-BinaryHash
            $checks = @{'invalid-configuration' = 2; 'terminal-unavailable' = 1}
            foreach ($name in $checks.Keys) {
                $receipt = Get-Content -LiteralPath (Join-Path $reportRoot "$name.json") -Raw | ConvertFrom-Json
                if ($receipt.test -ne $name -or $receipt.executable -ne "$ArtifactName.exe" -or
                    $receipt.sha256 -ne $binaryHash -or $receipt.expected_exit -ne $checks[$name] -or
                    $receipt.actual_exit -ne $checks[$name]) {
                    throw "Missing or mismatched smoke evidence for $name"
                }
            }
            "SHA256=$binaryHash" | Set-Content -LiteralPath (Join-Path $repoRoot 'sha256.txt') -Encoding utf8
            Write-Output "Packaging the smoke-tested binary without rebuilding: SHA256=$binaryHash"
        }
    }
}
finally {
    Pop-Location
}
