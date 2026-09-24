# Test Strategy — v0.1.3 development

## Contract tests

Verify:

- `CapabilityDescriptor` validation;
- `RuntimeInformationContract` validation;
- schema version handling;
- immutable contract behavior.

## Serialization tests

Verify JSON serialization and reconstruction of capability and runtime information contracts.

## Registry tests

Verify:

- capability registration;
- validation during registration;
- immutable runtime discovery behavior.

## Command integration tests

Verify:

- `agent.get_capabilities` execution;
- `agent.get_runtime_info` execution;
- CommandResult integration;
- deterministic error mapping.

## Architecture isolation

Reject dependencies from capability components on:

- HTTP transport;
- persistence;
- MetaTrader5 infrastructure;
- external frameworks.

## Regression

Retain v0.0.9 lifecycle, security ordering, transport behavior, error mapping, composition, and observability tests.

## Local repair verification (2026-09-17)

The capability contracts and provider modules were originally committed under the
incorrect version directory and removed during cleanup. They now live under
the active source tree (now `agent/`, previously `Version 0_0_9/agent`). Tests supply the existing required Command timestamp and
inject a provider that returns the documented contract objects.

Coverage includes provider payloads, command identity, HTTP serialization,
composition, current lifecycle snapshots, authorization rejection, unsupported
schemas, sanitized provider errors, blank contract identity validation, and
shallow metadata immutability. Registry membership is copied to a tuple; nested
metadata freezing and validation of arbitrary registry inputs are not implemented.

The default composition keeps the existing empty capability registration and
reports the actual Agent identity. Calling build_dispatcher without a provider
preserves the baseline command set.

## Maintenance regressions

Status tests exercise custom identity, created/running/stopped/failed states,
command identity and the composed HTTP response. CI helper tests use temporary
Git repositories and inert binary fixtures to test tag/commit validation,
no-MT5 confirmation, and packaging rejection of missing or mismatched evidence.
These fixture tests never launch MT5 and do not substitute for executable smoke
validation. They require Git and PowerShell 7; otherwise pytest reports skips.

## Target testing gates — planned

The production design adds schema/contract compatibility, persistence and crash
recovery, idempotency, priority/fairness, transfer integrity and bounded-memory,
transport, security/redaction, controlled Real-MT5, Windows-hosting, failure
injection and release-acceptance layers. No test may submit a financially
consequential real trade without explicit authorization and a safe environment.
The detailed gate matrix is in [ROADMAP.md](ROADMAP.md).

Mandatory safety scenarios before any execution capability include duplicate
delivery, identical command retry, expired trade, cancellation before/after the
point of no return, lost response after submission, crash after submission,
ambiguous restart and reconciliation disagreement. These tests use fakes or a
controlled demo environment only; CI never performs a real-money trade.
