# Changelog

This record consolidates the release documents present at
`1a133e6c6ea1b02a039f45610182037d347390ba` and the existing Git tags. Historical
verification statements below describe those records, not fresh validation of
old binaries. Release assets and publication dates have not been independently
revalidated here, so no publication dates are inferred from commit timestamps.

## [Unreleased] — v0.1.3 development

### Changed

- CI now automatically fails safe and runs the terminal-unavailable smoke only after
  the Agent's packaged inspection proves the dedicated runner has no discoverable MT5.
- Added a separate, inspection-only MT5-runner smoke for the reference installation
  and data environment; it never starts or terminates MT5.
- Added retained MT5-runner session and process-ownership probe evidence before any
  future controlled terminal or Agent runtime attempt.
- Documented the product boundary, target architecture, dependency-aware roadmap,
  GitLab planning package and Persian Wiki source. These are planning artifacts;
  they do not add Kafka, SQLite, trading, mTLS, service hosting, or remote-command
  execution.

### Added

- Versioned local command registry, capability classes and deterministic capability
  manifest with fail-closed command/version and enablement validation.
- Pure command-lifecycle, TTL/UTC expiration, cancellation/point-of-no-return and
  structured-error contracts; no execution or scheduler behavior is added.
- SQLite durable-command-state foundation with schema versioning, WAL, unique
  command identity and recovery queries; no outbox, cleanup or execution replay.
- Durable idempotency/correlation/reconciliation foundation: one execution identity
  per server command, explicit post-point-of-no-return ambiguity and no blind replay.
- Durable outbox with send-attempt versus acknowledgement semantics and resync snapshots.
- First pure-READ MT5 slice: terminal information, terminal version, and account
  information through explicit, typed allowlisted adapter calls only.

## [0.1.2] — Diagnostics, lifecycle logging, and dual-runner CI foundation

### Added

- Inspection-only `--diagnose` and `--diagnose --json`, with deterministic
  readiness exit codes and bounded Windows terminal/dependency/process checks.
- `--version` exits without initializing MT5 or entering the application host.
- Production lifecycle logging through the operational-observability port,
  configurable `MT5_AGENT_LOG_LEVEL` and optional best-effort `MT5_AGENT_LOG_FILE`.
- Regression coverage for CLI side effects, diagnostics, logging, confidentiality,
  and no-MT5 inspection gates without requiring real terminals in unit tests.

### Changed

- Canonical active version is 0.1.2; executable is `MT5Agent-v0.1.2.exe`.
- CI exercises packaged CLI modes and inspects the no-MT5 runner before the
  blocking manual confirmation; smoke rechecks absence before initialization.
- Normal no-argument startup retains vendor automatic terminal selection,
  existing exit codes and protocol behavior. No historical release is modified.

## [0.1.1] — Runtime identity and GitLab delivery maintenance

Released at `41a641d7d1a809bcb062b4785256a8a9189c95ba`, tag `v0.1.1`.
GitLab pipelines #7/#8/#9 and final-artifact Windows/MT5 manual acceptance
passed (maintainer-confirmed). Official executable SHA256:
`258c935737ca9ba0af03436f258d03d4043fd6d9851c73a32c03b38931393190`.
The tag and release remain immutable.

### Fixed

- `agent.get_status` reads the active AgentIdentity, preserving response fields
  and command/correlation IDs; regression coverage includes lifecycle states,
  custom identities and the composed HTTP path.
- Package version, default runtime identity and executable naming share
  `agent.__version__ = "0.1.1"`; the candidate is `MT5Agent-v0.1.1.exe`.
- PyInstaller uses its NumPy hook instead of hard-coded NumPy 2.x private
  imports, supporting the pinned NumPy 1.26.4 environment.

### Changed

- GitLab accepts stable `vMAJOR.MINOR.PATCH` tag pipelines alongside existing
  branch/MR pipelines and validates source version and checkout commit.
- Build and smoke evidence includes commit/pipeline identity and SHA256;
  packaging rejects mismatches and retains the smoke-tested binary unchanged.
- Terminal-unavailable smoke requires explicit confirmation at manual-job
  launch rather than hard-coding approval in YAML; running terminals are rejected.
- Retired the obsolete GitHub Actions workflow and refreshed canonical runtime,
  CI and release-checklist documentation. Generated outputs remain ignored.



## [0.1.0] — Capability discovery and canonical GitLab delivery

Released at `8fa282b55b726389e7ea2e36708b5b87864c7a60` (tag `v0.1.0`).
GitLab Release and Windows validate/test/build/smoke/package acceptance were
confirmed by the maintainer. Historical tag and release assets remain immutable.
The changes below record the work included in that release.

### Added

- Capability and runtime-information contracts, capability provider port and
  in-memory registry; `agent.get_capabilities` and `agent.get_runtime_info`
  integrated into the existing command/HTTP path.
- Capability validation, serialization, lifecycle snapshot, authorization and
  sanitized-provider-failure coverage in the active suite.
- Root console wrapper and pyproject configuration for the canonical package
  and root-only test collection.
- GitLab validate/test/build/smoke/package pipeline and shared PowerShell helper.
  The local Windows runner and both smoke paths passed before release.

### Changed

- Active source, tests, requirements, deployment recipe and current docs move
  from `Version 0_0_9` to the repository root layout.
- Historical version directories leave the active tree; their commits/tags
  remain unchanged. `Version 1_0_0` is not merged into the active runtime.
- GitLab is the development source of truth; GitHub remains downstream only.
  The legacy GitHub workflow was retained at this release snapshot.
- Release history is consolidated here and the deployment checklist becomes a
  fresh unchecked template.

### Fixed before this structural migration

- Capability modules originally placed in the wrong version directory were
  repaired in the active source, with matching tests (`8501e28`).
- Executable naming was aligned to `MT5Agent-v0.1.0.exe` (`566e14e`).
- Windows checkout workflow was simplified (`1a133e6`).

### Known limitations

Status-handler config/identity mismatch and inconsistent package/runtime/version
labels remained in v0.1.0 and are addressed in the v0.1.1 development section.
See [known issues](docs/KNOWN_ISSUES.md) for historical limitations.

## [0.0.9] — Operational Lifecycle Observability Foundation

- Added immutable operational events and event types, observer port and null
  observer, independent of request-level observability.
- Instrumented ApplicationHost startup/hosting/shutdown/failure paths; observer
  failures preserve primary lifecycle failures.
- Added lifecycle ordering, isolation and composition coverage.
- Consolidated Windows CI and restricted unnecessary PyInstaller collection.
- Historical records report Windows executable and MT5 startup validation.

Release record:

- PR #41; merge and peeled tag commit:
  `253afc7169afb0f5869625a7fc28bb9087ebb4e4`.
- Tag `v0.0.9`; GitHub Release recorded as `MT5 Agent v0.0.9`, published.
- Artifact: `MT5Agent-v0.0.9.exe`.
- Recorded executable SHA-256:
  `d7e1b3ebfd4380afd1749742c2c5c54561461ba40f0d8aedf787c34cd8534b07`.
- Source: baseline `docs/VERSION_HISTORY.md`. The changelog and several release
  documents under `Version 0_0_9` still described v0.0.8 and are not reattributed.

## [0.0.8] — Agent Hosting & Graceful Shutdown Foundation

- Added AgentLifecyclePort, HostingPort, ApplicationHost and deferred-binding
  HTTPServerHost, with process signal handling isolated in infrastructure.
- Added deterministic lifecycle exception containment, error precedence,
  resource cleanup, graceful shutdown and architecture-isolation tests.
- Preserved validation/authentication/authorization/dispatch ordering and
  best-effort request observability.
- Updated generated/local-file ignore policy and retained v0.0.7 release facts.

Release record:

- PR #40; merge commit: `a181b6364eb87597de10b0a781bbf45892d6cec9`.
- Tag `v0.0.8` points to reviewed implementation
  `ec0585624c4defd30c8d368be8756a33e2d3caa5`, intentionally distinct from merge.
- GitHub Release recorded as `MT5 Agent v0.0.8`, published.
- Artifact: `MT5Agent-v0.0.8.exe`.
- Recorded executable SHA-256:
  `e04f497bf3a893aa7bf5dec24bcc19d77930a50e42716dc7b1e5ace7d4641266`.
- Recorded successful final workflow: `35013801830`; manual Windows/MT5
  acceptance recorded controlled shutdown after terminal closure and Ctrl+C.
- Sources: VERSION_HISTORY and v0.0.8 changelog, audit and checklist, including
  copies retained under `Version 0_0_9` at the migration baseline.

## [0.0.7] — Agent Configuration & Composition Root Foundation

- Added immutable AgentConfig/HTTPTransportConfig, ConfigurationError and
  ConfigurationProvider; environment adapter and explicit composition root.
- Made HTTP host, port and body limit configurable while retaining Core isolation.
- Added configuration/composition/regression tests and Windows packaging/smokes.

Release record:

- PR #39; tag `v0.0.7`:
  `487db94c8a50f0db6c65d1e9f8fbcbd12aefa81d`.
- GitHub Release recorded as published; artifact `MT5Agent-v0.0.7.exe`.
- Recorded canonical published executable SHA-256:
  `38c17331fd3426c18f1c5774cafcdb4186f6810f529b9e1e548c91cf2db275e0`.
- PR #39 also refers to earlier artifact digests; those are not the canonical
  published executable checksum above.
- Sources: VERSION_HISTORY and `Version 0_0_7/CHANGELOG.md`.

## [0.0.6] — Concrete HTTP Transport Boundary Foundation

- Documents describe standard-library HTTP/JSON `POST /command`, deterministic
  error mapping, identity propagation, isolation and security-ordering tests.
- Documents describe Windows packaging, smoke testing and checksum generation.

Historical discrepancy (not corrected):

- Existing tag `v0.0.6` resolves to
  `4f052425842132dffc22ab79be857255f23c2e27`, the v0.0.5 documentation merge
  (PR #36). That tag's tree has no `Version 0_0_6` directory.
- The later v0.0.6 checklist itself cites this commit as its starting baseline
  and contains unchecked release gates. The current VERSION_HISTORY nevertheless
  lists v0.0.6 as a finalized baseline.
- Therefore this section records documented functionality and the actual tag
  separately; it does not certify that the tag contains the described code.
- No executable checksum or publication date is invented to fill that gap.
- Sources: VERSION_HISTORY, v0.0.6 changelog/checklist/audit and tag inspection.

## [0.0.5] — Security & Observability Boundary Foundation

- Added immutable security context/outcomes, authentication/authorization ports
  and ordering, deterministic failure results and identity propagation.
- Added immutable execution events, observer port and non-fatal telemetry.
- Added boundary/security/observability failure coverage and Windows packaging.

Release record:

- PR #35; merge/tag `v0.0.5`:
  `8c686e58070f561382c8c2280a1c9ccf8ddcd8de`.
- Historical audit records a published, non-draft, non-prerelease release.
- Artifact: `MT5Agent-v0.0.5.exe`.
- Recorded published executable SHA-256:
  `876ca0d8c238598bb47208dee1c998bdb0aed1d95d003609617966ea9b58969d`.
- Sources: v0.0.5 changelog, release notes, final audit and checklist.

## [0.0.4] — Transport Boundary & Execution Context Foundation

- Added immutable ExecutionContext/TransportRequest/TransportResponse,
  ApplicationPort and ApplicationBoundary over the command dispatcher.
- Preserved request/command/correlation identity and validated consistency.
- Added deterministic invalid-request handling, boundary tests and Windows CI.

Release record:

- PR #34; merge/peeled tag `v0.0.4`:
  `1f1a88632fd023439b5451b19c5851ff4f275bd3`.
- Artifact: `MT5Agent-v0.0.4.exe`.
- Recorded published executable SHA-256:
  `52a6e79823d1737cd6a6f2d8511db3038e3a7dafd71a418c45ae50b2fcfe908a`.
- Final audit records independent download, execution and checksum agreement;
  older unchecked checklist entries are not treated as overriding that record.
- Sources: v0.0.4 changelog, final audit and release notes.

## [0.0.3] — Agent Command Foundation

- Added immutable Command/CommandResult, schema validation, application
  dispatcher, deterministic results and read-only status/health commands.
- Added command/dispatcher tests and Windows executable/smoke/SHA256 pipeline.
- Tag `v0.0.3` peeled commit: `78d7f37e14d44c18ec62e3b242dc6a000af34681`.
- Release notes record successful CI verification and require the selected
  executable's checksum to be copied from its accompanying sha256.txt. No exact
  checksum is present in those reviewed records; none is inferred here.
- Sources: VERSION_HISTORY and v0.0.3 changelog/release notes/checklist.

## [0.0.2] — Agent Runtime & Contract Foundation

- Added lifecycle states, MT5Port, immutable runtime contracts, dependency
  injection, logging boundary, health and deterministic adapter failure handling.
- Added lifecycle/restart/exception regression coverage and Windows packaging.

Release record:

- PR #32 merge: `0ee540ef4af08a4bdcbb90b0262997b53d34662c`.
- Tag `v0.0.2` peeled commit: `cf12de73d90b78a29736ef45f1b9c287ed476b4f`.
- Recorded passing workflow: `34875680757`; unavailable-terminal exit code 1.
- Artifact: `MT5Agent-v0.0.2.exe`.
- Release notes/checklist executable SHA-256:
  `5ceae12da14f349cb2a3a4bd04606fdb2ca6b595e89183bb59d7a5de00dfe13f`.
- Corresponding CI artifact archive digest (not the EXE checksum):
  `359b6ae4e64d1905b5e6dc9d49fbc5efe8338106c56524879adb21852c57d893`.
- The architecture document contains a different verification EXE hash:
  `eb18b139572670ab98995d6ce34681c17ce9516011e65c000b0f9934fbc92ad0`.
  The records are inconsistent; the published asset was not revalidated here.
- Some documents still say publication is pending even though the tag exists.
  Tag existence does not independently prove release-asset publication.
- Sources: v0.0.2 changelog, architecture, release notes and checklist.

## [0.0.1] — Initial MT5 Lifecycle Foundation

- Added minimal Agent start/stop lifecycle, MT5 adapter, immutable Status,
  health helper, local transport and fake-adapter unit tests.
- Added Windows PyInstaller packaging, NumPy safeguards, icon rendering and
  CI/release artifact workflow.
- Historical changelog records controlled unavailable-terminal behavior,
  packaged native dependencies and manual Windows/MT5 execution.
- Tag `v0.0.1` peeled commit: `97c775278108607b8af251a9d219454c81f6b3d9`.
- Artifact: `MT5Agent-v0.0.1.exe`.
- Recorded final-verification executable SHA-256:
  `a96f7ce0b44ad81ee64dbabd739e844c601b3f5acea1d2897ea962221b18e608`.
  This identifies that verified binary; any rebuild needs a new checksum.
- Source: `Version 0_0_1/CHANGELOG.md` and VERSION_HISTORY.

## Historical scope and provenance

The 0.0.x foundation line deliberately excluded trading/order execution,
strategy/AI, durable persistence, Kafka/Gateway and Windows Service integration.
Files from the separate historical `Version 1_0_0` runtime do not establish
support for those features in this development line.

All original paths cited above are recoverable from the migration baseline via
`git show '<baseline>:<path>'`; see [migration map](docs/MIGRATION.md).
Existing tags, including discrepancies, are preserved without moving them.
