param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('metadata', 'validate', 'test', 'build', 'smoke-invalid', 'inspect-terminal', 'smoke-unavailable', 'smoke-available', 'probe-mt5-runtime', 'package')]
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

function Assert-ReferenceTerminal {
    $identity = (& whoami).Trim()
    $expectedExe = 'C:\Program Files\MetaTrader 5\terminal64.exe'
    $expectedData = 'C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075'
    $origin = Join-Path $expectedData 'origin.txt'
    if ($identity -notmatch 'MANI-PC\\Administrator$') { throw 'Unexpected MT5 runner identity' }
    if (-not (Test-Path -LiteralPath $expectedExe -PathType Leaf) -or -not (Test-Path -LiteralPath $origin -PathType Leaf)) { throw 'Expected MT5 reference environment is unavailable' }
    $originValue = (Get-Content -LiteralPath $origin -Raw).Trim()
    if ($originValue -ne 'C:\Program Files\MetaTrader 5') { throw 'Reference MT5 data environment does not map to the expected installation' }
    $inspection = Test-CandidateCLI
    if ($inspection.terminal.supported -ne $true -or $inspection.terminal.dependency_available -ne $true -or
        $inspection.terminal.errors.Count -ne 0 -or $inspection.terminal.paths -notcontains $expectedExe) { throw 'Agent inspection did not find the expected MT5 installation' }
    Write-Output "MT5 runner identity=$identity; APPDATA=$env:APPDATA; LOCALAPPDATA=$env:LOCALAPPDATA"
}

function Get-ReferenceTerminalProcesses {
    $expectedExe = 'C:\Program Files\MetaTrader 5\terminal64.exe'
    try {
        $processes = @(Get-CimInstance Win32_Process -Filter "Name = 'terminal64.exe'" |
            Where-Object { $_.ExecutablePath -and $_.ExecutablePath -ieq $expectedExe })
    }
    catch {
        throw 'Cannot determine reference MT5 process ownership'
    }
    return $processes
}

function Get-ProcessSessionId {
    param([int]$ProcessId)
    try {
        return (Get-Process -Id $ProcessId -ErrorAction Stop).SessionId
    }
    catch {
        throw "Cannot determine session for process $ProcessId"
    }
}

function Write-Mt5RuntimeProbe {
    Assert-ReferenceTerminal
    $currentProcess = Get-Process -Id $PID -ErrorAction Stop
    $parentId = (Get-CimInstance Win32_Process -Filter "ProcessId = $PID" -ErrorAction Stop).ParentProcessId
    $referenceProcesses = @(Get-ReferenceTerminalProcesses)
    $hash = Get-BinaryHash
    $receipt = [ordered]@{
        test = 'mt5-runtime-probe'
        executable = "$ArtifactName.exe"
        sha256 = $hash
        source_commit = $sourceCommit
        pipeline_id = $pipelineId
        expected_exit = 0
        actual_exit = 0
        runner_identity = (& whoami).Trim()
        runner_process_id = $PID
        runner_session_id = $currentProcess.SessionId
        runner_parent_process_id = $parentId
        runner_parent_session_id = Get-ProcessSessionId -ProcessId $parentId
        reference_terminal = 'C:\Program Files\MetaTrader 5\terminal64.exe'
        pre_existing_reference_mt5 = ($referenceProcesses.Count -gt 0)
        pre_existing_reference_mt5_processes = @($referenceProcesses | ForEach-Object {
            [ordered]@{ process_id = $_.ProcessId; session_id = Get-ProcessSessionId -ProcessId $_.ProcessId; executable = $_.ExecutablePath }
        })
        ci_started_mt5 = $false
        agent_started = $false
        runtime_attempted = $false
    }
    $receipt | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $reportRoot 'mt5-runtime-probe.json') -Encoding utf8
    Write-Output "MT5 runtime probe: runner_session=$($currentProcess.SessionId); pre_existing_reference_mt5=$($receipt.pre_existing_reference_mt5)"
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
            foreach ($name in @('build', 'invalid-configuration', 'terminal-unavailable', 'terminal-available', 'mt5-runtime-probe')) {
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
        'smoke-available' {
            Assert-ReferenceTerminal
            $hash = Get-BinaryHash
            [ordered]@{ test='terminal-available'; executable="$ArtifactName.exe"; sha256=$hash; source_commit=$sourceCommit; pipeline_id=$pipelineId; expected_exit=0; actual_exit=0 } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportRoot 'terminal-available.json') -Encoding utf8
        }
        'probe-mt5-runtime' {
            Write-Mt5RuntimeProbe
        }
        'package' {
            $checksumPath = Join-Path $repoRoot 'sha256.txt'
            if (Test-Path -LiteralPath $checksumPath) { Remove-Item -LiteralPath $checksumPath }
            Assert-BuildEvidence
            $binaryHash = Get-BinaryHash
            $checks = @{'invalid-configuration' = 2; 'terminal-unavailable' = 1; 'terminal-available' = 0; 'mt5-runtime-probe' = 0}
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
