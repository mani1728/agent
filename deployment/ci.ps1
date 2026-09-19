param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('metadata', 'validate', 'test', 'build', 'smoke-invalid', 'inspect-terminal', 'smoke-unavailable', 'package')]
    [string]$Task,
    [string]$PythonExecutable = 'python',
    [string]$ArtifactName = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$versionSource = Get-Content -LiteralPath (Join-Path $repoRoot 'agent/__init__.py') -Raw
$versionMatch = [regex]::Match($versionSource, '(?m)^__version__ = "((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))"\r?$')
if (-not $versionMatch.Success) { throw 'Missing stable semantic version in agent/__init__.py' }
$version = $versionMatch.Groups[1].Value
$expectedArtifactName = "MT5Agent-v$version"
if ($ArtifactName -and $ArtifactName -ne $expectedArtifactName) {
    throw "ArtifactName must match the source version: $expectedArtifactName"
}
$ArtifactName = $expectedArtifactName
$env:ARTIFACT_NAME = $ArtifactName
if ($env:CI_COMMIT_TAG -and $env:CI_COMMIT_TAG -cne "v$version") {
    throw "Tag $env:CI_COMMIT_TAG does not match source version v$version"
}
$sourceCommit = (& git -C $repoRoot rev-parse HEAD)
if ($LASTEXITCODE -ne 0) { throw 'Cannot determine source commit' }
if ($env:CI_COMMIT_SHA -and $env:CI_COMMIT_SHA -ne $sourceCommit) {
    throw 'Checkout HEAD does not match CI_COMMIT_SHA'
}
$pipelineId = [string]$env:CI_PIPELINE_ID
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

function Assert-BuildEvidence {
    $build = Get-Content -LiteralPath (Join-Path $reportRoot 'build.json') -Raw | ConvertFrom-Json
    if ($build.executable -ne "$ArtifactName.exe" -or $build.version -ne $version -or
        $build.sha256 -ne (Get-BinaryHash) -or $build.source_commit -ne $sourceCommit -or
        $build.pipeline_id -ne $pipelineId) {
        throw 'Missing or mismatched build evidence for this commit/pipeline'
    }
}

function Invoke-CandidateCommand {
    param([string]$Name, [string[]]$Arguments)
    $stdout = Join-Path $reportRoot "$Name.stdout.log"
    $stderr = Join-Path $reportRoot "$Name.stderr.log"
    $process = Start-Process -FilePath $exePath -ArgumentList $Arguments -WorkingDirectory $repoRoot `
        -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    try {
        if (-not $process.WaitForExit(30000)) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            throw "$Name exceeded the 30-second inspection limit"
        }
        $process.WaitForExit()
        return [pscustomobject]@{ ExitCode = $process.ExitCode; Output = (Get-Content $stdout -Raw) }
    }
    finally { $process.Dispose() }
}

function Test-CandidateCLI {
    Assert-BuildEvidence
    $versionResult = Invoke-CandidateCommand -Name 'version' -Arguments @('--version')
    if ($versionResult.ExitCode -ne 0 -or $versionResult.Output.Trim() -cne $version) {
        throw 'Executable --version failed or disagrees with source metadata'
    }
    $result = Invoke-CandidateCommand -Name 'diagnostics' -Arguments @('--diagnose', '--json')
    $inspection = $result.Output | ConvertFrom-Json
    $expectedExit = if ($inspection.ready) { 0 } else { 1 }
    if ($result.ExitCode -ne $expectedExit -or $inspection.agent_version -ne $version -or
        $inspection.inspection_only -ne $true -or $inspection.configuration.valid -ne $true -or
        $inspection.terminal.dependency_available -ne $true) {
        throw 'Executable diagnostics failed validation'
    }
    Assert-BuildEvidence
    return $inspection
}

function Assert-NoTerminal {
    if (Get-Process -Name terminal,terminal64,metatrader,metatrader64 -ErrorAction SilentlyContinue) {
        throw 'A terminal is running; refuse terminal-unavailable smoke'
    }
    $inspection = Test-CandidateCLI
    if ($inspection.terminal.supported -ne $true -or $inspection.terminal.process_running -ne $false -or
        @($inspection.terminal.paths).Count -ne 0 -or @($inspection.terminal.errors).Count -ne 0) {
        throw 'Terminal present or inspection incomplete; no-MT5 confirmation is unsafe'
    }
    Write-Output 'No-MT5 preflight: no terminal process or executable found in inspected locations'
    Write-Output ($inspection.terminal.searched_locations -join '; ')
}

function Invoke-Smoke {
    param([string]$Name, [int]$ExpectedExit, [string]$ExpectedErrorPattern)
    Assert-BuildEvidence
    # A failed rerun must not leave a prior successful receipt behind.
    $receiptPath = Join-Path $reportRoot "$Name.json"
    if (Test-Path -LiteralPath $receiptPath) { Remove-Item -LiteralPath $receiptPath }
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
            source_commit = $sourceCommit
            pipeline_id = $pipelineId
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
        'metadata' {
            Write-Output "Source $sourceCommit; version $version; executable $ArtifactName.exe"
        }
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
            # Prevent stale executables/evidence from being uploaded after a failed build.
            if (Test-Path -LiteralPath $exePath) { Remove-Item -LiteralPath $exePath }
            foreach ($name in @('build', 'invalid-configuration', 'terminal-unavailable')) {
                $receiptPath = Join-Path $reportRoot "$name.json"
                if (Test-Path -LiteralPath $receiptPath) { Remove-Item -LiteralPath $receiptPath }
            }
            Invoke-Python -Arguments @('deployment/make_icon.py')
            Invoke-Python -Arguments @('-m', 'PyInstaller', 'deployment/Agent.spec', '--clean', '--noconfirm')
            [ordered]@{
                executable = "$ArtifactName.exe"
                version = $version
                sha256 = Get-BinaryHash
                source_commit = $sourceCommit
                pipeline_id = $pipelineId
            } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportRoot 'build.json') -Encoding utf8
            Write-Output "Built $exePath; SHA256=$(Get-BinaryHash)"
        }
        'smoke-invalid' {
            $null = Test-CandidateCLI
            $previousPort = [Environment]::GetEnvironmentVariable('MT5_AGENT_HTTP_PORT', 'Process')
            try {
                $env:MT5_AGENT_HTTP_PORT = 'invalid'
                Invoke-Smoke -Name 'invalid-configuration' -ExpectedExit 2 -ExpectedErrorPattern 'Invalid startup configuration: MT5_AGENT_HTTP_PORT must be an integer'
            }
            finally {
                [Environment]::SetEnvironmentVariable('MT5_AGENT_HTTP_PORT', $previousPort, 'Process')
            }
        }
        'inspect-terminal' {
            Assert-NoTerminal
        }
        'smoke-unavailable' {
            $receiptPath = Join-Path $reportRoot 'terminal-unavailable.json'
            if (Test-Path -LiteralPath $receiptPath) { Remove-Item -LiteralPath $receiptPath }
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

                Assert-NoTerminal
                Invoke-Smoke -Name 'terminal-unavailable' -ExpectedExit 1 -ExpectedErrorPattern '\(agent_start_failed\)'
            }
            finally {
                foreach ($name in $names) {
                    [Environment]::SetEnvironmentVariable($name, $previousValues[$name], 'Process')
                }
            }
        }
        'package' {
            $checksumPath = Join-Path $repoRoot 'sha256.txt'
            if (Test-Path -LiteralPath $checksumPath) { Remove-Item -LiteralPath $checksumPath }
            Assert-BuildEvidence
            $binaryHash = Get-BinaryHash
            $checks = @{'invalid-configuration' = 2; 'terminal-unavailable' = 1}
            foreach ($name in $checks.Keys) {
                $receipt = Get-Content -LiteralPath (Join-Path $reportRoot "$name.json") -Raw | ConvertFrom-Json
                if ($receipt.test -ne $name -or $receipt.executable -ne "$ArtifactName.exe" -or
                    $receipt.sha256 -ne $binaryHash -or $receipt.expected_exit -ne $checks[$name] -or
                    $receipt.source_commit -ne $sourceCommit -or $receipt.pipeline_id -ne $pipelineId -or
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
