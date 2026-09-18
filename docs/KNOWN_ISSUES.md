# Known issues outside the structural migration

These are existing issues, not fixes included in the stage-1 layout migration.
Historical paths below refer to baseline
`1a133e6c6ea1b02a039f45610182037d347390ba` and remain accessible with `git show`.

## KI-001: status handler uses a removed attribute

`agent/application/app.py` reads `agent.config.version` and
`agent.config.app_name` for `agent.get_status`. The active `Agent` exposes
`identity`, not `config`. The dispatcher contains the resulting exception and
returns `execution_failed`. Resolve and test this in a separate behavioral fix.

## KI-002: version metadata is inconsistent

- `agent/__init__.py`: `__version__ = "0.0.6"`.
- `agent/contracts/models.py`: `AgentIdentity.version = "0.0.8"`.
- Development README label and executable filename: v0.1.0.
- The new pyproject reads the existing package version without changing it.

Choose and test a single version authority separately. Stage 1 neither changes
runtime identity nor creates a v0.1.0 tag or release.

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

Stage 1 preserves the six active test files byte-for-byte. Historical tests
`test_agent.py` (latest at `Version 0_0_2/tests/`) and `test_commands.py`,
`test_dispatcher.py`, `test_security_observability.py`, `test_transport.py`
(latest at `Version 0_0_5/tests/`) remain recoverable from the baseline.
Some import the old `contracts.models.AgentConfig`; they need API adaptation
and coverage review in a separate task, not blind collection in this migration.
