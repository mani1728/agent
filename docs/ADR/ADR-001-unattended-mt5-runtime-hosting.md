# ADR-001: Unattended MT5 Runtime Hosting on Windows

**Status:** experiment required; no production topology approved.  
**Decision context:** the control-plane service runs in Session 0, while the
MetaTrader5 Python package communicates with a GUI-dependent terminal. Pipeline
#16 proved Session 0 ownership evidence, not safe direct runtime integration.

## Decision

Keep the durable Agent control plane as an automatic Windows Service. Do not
claim that it directly owns MT5 IPC. Evaluate a least-privilege, session-bound
MT5 Runtime Worker supervised through authenticated local IPC; a per-user
scheduled-task launch is a candidate, not a decision. Desktop-interaction
services, user-process termination, credential exposure and trading are rejected.

## Controlled non-trading experiment

Run only in an isolated/demo environment with an already-authorized terminal.
Record process/session ownership, terminal discovery, `initialize`, `version`,
`terminal_info`, and optional safely available `account_info`; test readiness and
the Worker-to-Service IPC boundary. Never place/modify/cancel orders, close
positions, delete pending orders, or broadly kill `terminal64.exe`.

**Success:** a documented session-bound worker initializes the one supported
terminal; control-plane/service separation and shutdown ownership are proven;
no user-owned process is harmed; safe diagnostic evidence is retained.
**Failure:** Session 0 access is required, IPC cannot be authenticated, MT5 cannot
be reliably initialized, or cleanup/ownership is unsafe. Failure preserves the
current inspection-only approach and blocks runtime implementation.

## Acceptance and follow-up

Add a reproducible test procedure, redacted evidence schema, rollback/cleanup
rules, and an explicit decision record. Production Worker implementation depends
on this ADR passing and product-owner acceptance.
