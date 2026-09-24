# ADR-001: Unattended MT5 Runtime Hosting on Windows

**Status:** provisional; interactive-session viability demonstrated, unattended
launch mechanism not yet demonstrated.
**Decision context:** the control-plane service runs in Session 0, while the
MetaTrader5 Python package communicates with a GUI-dependent terminal. Pipeline
#16 proved Session 0 ownership evidence, not safe direct runtime integration.

## Decision

Keep the durable Agent control plane as an automatic Windows Service. Do not
claim that it directly owns MT5 IPC. Evaluate a least-privilege, session-bound
MT5 Runtime Worker supervised through authenticated local IPC; a per-user
scheduled-task launch is a candidate, not a decision. Desktop-interaction
services, user-process termination, credential exposure and trading are rejected.

## Experiment evidence (2026-09-24)

**Verified:** the GitLab Runner process ran as `MANI-PC\Administrator` in
Session 0. The experiment shell and its `Explorer.EXE` evidence ran as the same
identity in Session 1. No reference terminal existed before the probe. A
non-production worker, launched directly from Session 1 with the explicit
`C:\Program Files\MetaTrader 5\terminal64.exe` path, used the repository `.venv`
(64-bit Python 3.14.7; MetaTrader5 5.0.6180). It successfully called
`initialize`, `version`, `terminal_info`, and a read-only `account_info` presence
check; account data was not persisted. It then called `shutdown` and exited 0.

The terminal created during initialization had the worker PID as parent, ran as
`MANI-PC\Administrator` in Session 1, and remained running immediately after
Python API shutdown. No pre-existing terminal or user process was stopped. The
ignored, redacted local result is `reports/adr-001-mt5-runtime-hosting.json`;
the repeatable harness is `tools/experiments/mt5_runtime_hosting_probe.py`.

**Not tested:** boot without a user session, automatic/logon Task Scheduler
launch, locked or disconnected session behavior, terminal restart, Worker restart
supervision, service-to-Worker IPC, or Python 3.11 production compatibility.

## Candidate evaluation

| Candidate | Evidence | Outcome |
| --- | --- | --- |
| Service directly hosts MT5 | Runner is Session 0; no GUI-service hack attempted. | Blocked/rejected pending contrary safe evidence. |
| Scheduled Task in interactive context | Task Scheduler is available, but no dedicated MT5 task was created or exercised. | Plausible candidate; untested. |
| Direct session-bound Worker | Direct Session 1 probe successfully initialized/read/shutdown against reference MT5. | Viable interactive execution mechanism; not unattended. |

## Controlled non-trading experiment

Run only in an isolated/demo environment with an already-authorized terminal.
Record process/session ownership, terminal discovery, `initialize`, `version`,
`terminal_info`, and optional safely available `account_info`; test readiness and
the Worker-to-Service IPC boundary. Never place/modify/cancel orders, close
positions, delete pending orders, or broadly kill `terminal64.exe`.

**Observed success:** session-bound MT5 API viability and non-destructive Python
API shutdown were proven. **Incomplete acceptance:** a supported unattended
launcher, authenticated IPC, supervisor recovery and boot/session-state behavior
remain unproven. The production Worker implementation remains blocked.

## Acceptance and follow-up

The next experiment must create a narrowly scoped Task Scheduler or other
supported launcher in an authorized test context and collect boot/logon/locked or
disconnected-session evidence. Future ownership rules must track Worker instance,
PID, creation/session identity and launch metadata; they must never broadly kill
`terminal64.exe` processes. Service-to-Worker IPC should use authenticated local
framing (for example Named Pipes protected by explicit ACLs), with service and
Worker identities, replay/versioning and least-privilege rules specified before
implementation.
