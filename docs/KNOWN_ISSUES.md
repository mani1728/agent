# Known issues and maintenance status

## Resolved in v0.1.1 development

- **KI-001:** `agent.get_status` now reads `agent.identity.version` and
  `agent.identity.app_name`. Regression tests cover the real dispatcher and
  composed HTTP path without adding a compatibility `config` attribute.
- **KI-002:** `agent.__version__` is the authority for package metadata,
  default runtime identity and executable naming. CI rejects mismatching tags.

## Remaining historical issues

Historical paths below refer to baseline
`1a133e6c6ea1b02a039f45610182037d347390ba` and remain accessible with `git show`.

## KI-008: Session 0 blocks a Real-MT5 runtime claim

Pipeline #16 recorded that the MT5 runner service executes in Windows Session 0.
The MetaTrader5 Python package uses terminal IPC, and no safe real-runtime test
has demonstrated that this GUI-dependent path works from Session 0. The current
probe is deliberately inspection-only; it does not start, stop, or kill any
user-owned `terminal64.exe`. A production Windows-hosting decision is required
before claiming unattended MT5 integration. See [TARGET_ARCHITECTURE.md](TARGET_ARCHITECTURE.md).

## KI-003: historical Worker is syntactically incomplete

`Version 1_0_0/agent/core/worker.py` ends inside a string literal at line 981 in
the baseline. It cannot be parsed. It is retained in Git history and is not
imported, repaired, or incorporated into the active runtime.

## KI-004: historical Kafka packaging references missing paths

`Version 1_0_0/agent/deployment/KafkaAgent.spec` refers to missing
`agent/config.example.json` and hidden import `agent.transport.kafka_transport`;
the tracked module was under `agent/transport/kafka/kafka_transport.py`.
This spec is historical only and is not reused by the canonical build.

## KI-005: historical release documents contain stale labels

Several documents inside `Version 0_0_9`, including CHANGELOG, RELEASE_NOTES,
FINAL_AUDIT and RELEASE_CHECKLIST, still describe v0.0.8. Their original contents
remain in history. The root changelog attributes those facts to v0.0.8; it does
not relabel them as proof of v0.1.0 validation. The new deployment checklist is
an unchecked template, not a retroactive modification of release evidence.

## KI-006: historical tag and checksum discrepancies need reconciliation

- `v0.0.6` resolves to `4f052425842132dffc22ab79be857255f23c2e27`, a v0.0.5
  documentation merge whose tree contains no `Version 0_0_6`. Later documents
  describe v0.0.6 HTTP functionality. Both facts are recorded in CHANGELOG.md;
  the tag must not be moved as part of this migration.
- The v0.0.2 architecture document records a different executable hash from
  the later release notes/checklist. Both hashes are preserved with provenance.
  Published release assets have not been re-downloaded in this migration.

## KI-007: older regression suites are not part of the current suite

The migration preserved six active test files; v0.1.1 adds targeted regressions. Historical tests
`test_agent.py` (latest at `Version 0_0_2/tests/`) and `test_commands.py`,
`test_dispatcher.py`, `test_security_observability.py`, `test_transport.py`
(latest at `Version 0_0_5/tests/`) remain recoverable from the baseline.
Some import the old `contracts.models.AgentConfig`; they need API adaptation
and coverage review in a separate task, not blind collection in this migration.
