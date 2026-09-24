# Capability Roadmap: v0.1.3 to v1.0.0

**Status:** proposed, dependency-gated; no dates are asserted. “Implemented”
means repository evidence, not a future promise.

| Phase / status | Objective and prerequisites | Deliverables and acceptance evidence |
| --- | --- | --- |
| Current v0.1.3 — partial | Finish the existing lifecycle/HTTP/diagnostic/CI foundation. Prerequisite: none. | **Ready now:** correct version/status documentation, contract/error-model terminology, CI evidence retention and a controlled Session 0 experiment plan. Acceptance: existing tests plus documentation review; no live MT5 launch. |
| A: decisions and contracts — decided/planned | Product-owner safety, capability classes, TTL, correlation and config boundaries are decided; service topology still needs evidence. | Versioning policy, envelope/error/transfer schemas, capability manifest, ACL policy and architecture decision records. Schema/property/negative tests; security review. |
| B: controlled runtime integration — partial/blocked | Session 1 direct Worker/API viability is verified; demonstrate a supported one-terminal unattended launcher outside unsafe Session 0 assumptions. | Authorized Task Scheduler or equivalent experiment, ownership-safe rules, readiness semantics. Controlled integration tests; no financial trade. |
| C: durable command core — planned | A and B. | SQLite WAL migrations, command state machine, idempotency/outbox/recovery/quota model. Crash/disk-full/corruption/failure-injection tests. |
| D: read capabilities — planned | A–C. | Allowlisted terminal/account/symbol/history operations and safe MT5 result normalization. Contract, UTC/history-limit and mock/Real-MT5 read tests. |
| E: bulk transfer — planned | C and D. | Partition planner, bounded serializer/chunks/manifest/hash/ack/resume/cancel. GB-scale bounded-memory, duplicate/missing chunk and resume tests. |
| F: transport and observability — planned | C; Kafka environment. | Kafka adapter with durable acknowledgements, HTTPS mTLS bootstrap/recovery, structured logs/telemetry/heartbeat. Security, outage/backpressure and redaction tests. |
| G: execution capabilities — requires decision | A–F plus explicit trading authorization. | Typed order lifecycle, correlation mapping, MT5 retcodes/partial outcome and non-repeat proof. Demo/sandbox test only; security/audit approval. |
| H: unattended production hardening — blocked | B and all prior phases. | Supported Windows supervision model, quiesce lifecycle, upgrades, release acceptance/runbooks. Boot/restart/recovery/service and operational acceptance tests. |
| v1.0.0 gate — future | All prior gates. | Security, recovery, load, compatibility, support and release evidence accepted; no unresolved critical blocker. |

## v0.1.3 completion proposal

**Ready now:** consolidate approved decisions, preserve CI/probe ownership
evidence, reconcile current version labels, and write a controlled
real-MT5/session-topology test protocol. **Ready after a small prerequisite:**
contract-design ADRs and capability schemas. **Requires experiment evidence:**
service/MT5 topology. **Defer:** Kafka, spooler, mTLS,
priority engine, large transfer and execution code. **Future/v1.0.0:** production
service hardening and commercial enrollment.

Each implementation issue must trace Product Requirement → capability phase →
acceptance tests → documentation. Security/operations/docs are mandatory fields,
not a closing task.
# Scheduler status

**IMPLEMENTED (foundation):** bounded local admission and deterministic effective-priority selection with FIFO tie breaking and cooperative cancellation exclusion. It is deliberately not an MT5 executor and introduces no parallel terminal calls. Durable queue persistence and production load validation remain **PLANNED / PENDING PRODUCTION VALIDATION**.

