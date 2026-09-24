# GitLab Planning Package

**Status:** planning baseline. The GitLab issues, labels, milestones, board lists
and Wiki pages are applied through authenticated GitLab access; this file remains
the version-controlled traceability source.

## Proposed labels and workflow

Use existing conventions when present; otherwise create `type::architecture`,
`type::security`, `type::documentation`, `type::ci`, `type::testing`,
`type::feature`; `status::planned`, `status::ready`, `status::in-progress`,
`status::blocked`, `status::validation`; and `component::mt5`, `component::transport`,
`component::persistence`, `component::service`, `component::observability`.
One board uses the status labels: Backlog, Ready, In progress, Blocked,
Validation/review, Done. Milestones are capability gates—not calendar promises:
`v0.1.3 completion`, `architecture-approved`, `runtime-proven`, `v1.0.0 readiness`.

## Engineering-sized issue set

| Title | Phase / labels | Dependency and acceptance summary |
| --- | --- | --- |
| Approve unattended MT5 hosting topology | A, `architecture`, `blocked`, `service`, `mt5` | Controlled Session 0 vs session-broker experiment; document safe topology and rollback. |
| Define versioned command, response and error contracts | A, `architecture`, `security` | Threat model and capability taxonomy; schemas, compatibility policy and negative tests. |
| Define identity, enrollment and credential lifecycle | A, `security` | Installation vs Agent vs entitlement separation; provision/rotate/revoke/reinstall acceptance. |
| Implement durable command/outbox/idempotency state | C, `feature`, `persistence` | Approved contracts; crash/restart, disk-full, retention and duplicate-execution tests. |
| Deliver read-only MT5 capability slice | D, `feature`, `mt5` | Runtime proof and persistence; typed read contracts, UTC/history-limit tests. |
| Deliver bounded historical-transfer protocol | E, `feature`, `transport`, `testing` | Read slice and outbox; partition/chunk/hash/resume/cancel/load acceptance. |
| Deliver Kafka and HTTPS control adapters | F, `feature`, `transport`, `security` | Durable core; mTLS/ack/outage/backpressure/redaction tests. |
| Deliver observability and support controls | F, `feature`, `observability` | Durable state; liveness/readiness, safe heartbeat/log rotation/support runbook. |
| Decide and implement typed execution capability slice | G, `architecture`, `security`, `mt5` | Explicit product authorization; sandbox-only non-duplicate/retcode/correlation evidence. |
| Production unattended hardening and release gate | H, `feature`, `service`, `blocked` | All dependencies; boot/recovery/quiesce/upgrade/release acceptance. |

Every issue description must include purpose, context, scope, non-goals,
dependencies, acceptance criteria, tests, security/operational/documentation
impact and a link to its roadmap phase. Parent/child work items can express the
phase hierarchy if supported; otherwise use issue links and the dependency table.

## Applied GitLab planning state

The authenticated project now has the taxonomy above, six capability-gate
milestones, and work items `#1`–`#16`. The `Development` board has lists for
`status::planned`, `status::ready`, `status::in-progress`, `status::blocked`,
`status::validation`, and `status::done`. Native issue blocking links are not
available under this GitLab license (HTTP 403); the dependency graph below and
[TRACEABILITY.md](TRACEABILITY.md) are the authoritative workaround.

```text
#1 runtime ADR ───────────────┐
#2 protocol/manifest → #3 lifecycle/errors → #4 SQLite → #5 idempotency → #14 execution
                    └────────────────────────→ #7 read → #8 transfer ───────┐
#4 SQLite → #6 outbox/resync ────────────────────────────────────────────────┤
#12 identity/authz → #11 config and #13 transport ───────────────────────────┤
                                                                    → #16 readiness
```
