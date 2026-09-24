# Target Architecture and Decisions

**Status:** proposed architecture for review; only the current HTTP/lifecycle
foundation is implemented. **Principle:** the Server thinks; the Agent executes,
retrieves, protects, persists, reports and recovers. The Agent never contains AI,
trading strategy, risk or capital-management decisions.

## Boundary and topology

```text
Server / control plane (decisions, IAM, strategy, risk, scheduling)
  │ versioned, authenticated commands and acknowledgements
  ▼
Transport ports (Kafka primary; HTTPS mTLS bootstrap/recovery)
  ▼
Ingress → validate → authenticate → authorize → durable command state
  ▼                         │
Priority scheduler ─────────┤ (one serialized MT5-operation lane)
  ▼                         ▼
Capability handlers / MT5 port → one MT5 terminal → result/transfer producer
  ▼
SQLite WAL outbox + command/transfer/idempotency state → transport egress
```

One installation/runtime of `C:\Program Files\MetaTrader 5\terminal64.exe` is
in scope per client. Account identity is not a reason to add multi-terminal
orchestration.

## Decisions proposed for approval

| Area | Decision | Rationale / guardrail |
| --- | --- | --- |
| Service and Session 0 | Separate the durable Agent service/control process from a session-bound MT5 execution broker until a controlled experiment proves the supported topology. Prefer a per-user scheduled-task/interactive broker with authenticated local IPC, supervised by an automatic service. | Do not use desktop-interaction service hacks or kill terminals. A service directly calling MT5 IPC is **blocked** pending test evidence. |
| Capability model | Named, allowlisted, versioned operations with typed JSON parameters; no remote Python/code execution. | Enables API coverage without code injection. Read capabilities precede trade capabilities. |
| Command envelope | Do not freeze V1 yet. Require `schema_version`, immutable `command_id`, target `agent_id`, operation, parameters, priority, created/expiry times, correlation ID, idempotency key, reply routing and signed/auth context. | Validate bounds/type/schema before authorization and durable acceptance. |
| Idempotency | Persist a command state machine keyed by `command_id` plus scoped idempotency key before MT5 side effects. A duplicate returns stored/in-progress result, never automatically repeats execution. | At-least-once delivery is transport behavior, not permission to repeat a trade. |
| State machine | `received → validated → authorized → accepted → execution_started → mt5_result_obtained → response_persisted → response_transmitted → server_acknowledged`; terminal states include rejected, expired, cancelled and recovery-required. | Supports crash recovery and auditability. |
| Priority | Three policy classes: urgent execution, normal control/read, bulk transfer; EDF within class plus bounded aging and per-class concurrency/backpressure. MT5 calls remain serialized until concurrency safety is demonstrated. | Bulk work yields between partitions; aging prevents starvation. |
| Large data | Partition MT5 retrieval by time/count, serialize incrementally, compress only after measurement, emit bounded chunks to disk-backed outbox. Each chunk carries transfer ID/index/byte count/hash; manifest carries whole hash/count/schema. | Never create a giant result array or payload. Server acks/resumes missing chunks. |
| Persistence | SQLite WAL with explicit schema migrations, transactionally coupled command/outbox records where possible, quotas, retention, corruption quarantine/rebuild procedure, disk-full degradation. | Durable outbound data and execution decisions; bounded disk/RAM. |
| Transport | Kafka producer/consumer behind ports; manual acknowledgement/offset commit only after durable handling. HTTPS+mTLS is control/bootstrap/recovery, not a hidden second business implementation. | Exactly-once broker semantics are not assumed. |
| Identity | Generate a random installation ID at provisioning; server assigns Agent ID and binds credentials. Treat hardware signal only as an optional, privacy-reviewed recovery signal. Keep customer, subscription, credential and device fingerprint distinct. | Hardware/MAC changes must not silently erase entitlement. |
| Security | mTLS, certificate rotation/revocation, signed/replay-bounded commands, deny-by-default capability ACL, payload/decompression limits, recursive redaction and least-privilege local storage. | Secrets are never source/config/log/telemetry payloads. |
| Health | Liveness says process/supervisor is alive; readiness says it can safely accept a class of work. Heartbeat reports version/state, MT5/transport/spool health, queue age/bytes, disk/CPU/memory and bounded safe error categories. | Offline is not the only unhealthy state. |
| Quiesce | States `RUNNING → QUIESCING → QUIESCED → RESUMING`, plus degraded/stopping. A minimal authenticated control/heartbeat channel remains alive while quiesced. | Policy for in-flight trades/transfer cancellation and restart recovery requires approval before behavior exists. |
| Logging | Structured local JSON logs with allowlisted fields, recursive redaction, rotation/retention/max-disk and support bundles. Server telemetry is curated separately. | Never ship raw support logs by default. |

## Product-owner decisions — decided, not implemented

The following supersede the earlier open-decision wording. Commands are explicit,
allowlisted product commands—not arbitrary Python or MT5 function names. Unknown
operations and unknown command versions fail closed with
`UNSUPPORTED_COMMAND`/`UNSUPPORTED_COMMAND_VERSION`. Handshake/resync publishes
a capability manifest containing Agent/protocol versions, commands and versions,
capability classes, and enabled/disabled state.

Capability authorization is both class- and command-level. Classes are `READ`,
`LOCAL_STATE`, `TRADE_ANALYSIS`, `TRADE_EXECUTION`, and future
`CHART_TERMINAL`; class permission never replaces individual-command validation.
Server-requested priority is constrained by local policy into `CRITICAL`, `HIGH`,
`NORMAL`, `LOW`, or `BULK`; bounded queues, aging and fairness apply. Retrieval
partition size and network chunk size are independent policies.

SQLite is the local durable correlation/recovery authority, mapping server command
to Agent execution, available MT5 request identifier, orders/deals/positions and
secondary short trace token. MT5 comments are never the authority. Retention is
configurable, but cleanup must not permit a duplicate trade: uncertain/unsafe
records remain protected or require reconciliation.

Commands have durable TTL/`expires_at` state; per-command expiration overrides
policy defaults and an expired command never executes after retry/restart.
Cancellation is lifecycle-aware and is not undo: after a trade point-of-no-return,
a new explicit command is required to reverse any effect. An uncertain `order_send`
result is `EXECUTION_AMBIGUOUS`; timeout, lost response or crash never authorizes
blind replay. Reconciliation uses observed MT5/broker orders, deals, positions and
history as authority for market state.

Remote configuration is versioned, authenticated, policy/compatibility validated,
durably staged, atomically applied, health checked and rolled back to last known
good state. Bootstrap trust/security anchors are `LOCAL_ONLY`; operational values
are `SERVER_MANAGED` or `SERVER_MANAGED_WITH_LIMITS`. Remote configuration cannot
cross local security boundaries.

## MT5 data and execution semantics

The official Python integration exposes terminal/account/symbol/tick/bar/order,
position/history, calculation and `order_send` functions; retrieved bars are
NumPy arrays. `copy_rates_range` is UTC-based and limited by terminal history and
“Max. bars in chart.” Therefore the read capability design must discover limits,
use UTC timestamps and partition requests before each MT5 call; a huge
`copy_rates_range()` then chunking it is rejected.

Write commands are a later, stricter capability family. The Agent performs only
technical validation (schema, terminal/symbol/market/protocol state) and returns
precise MT5 outcome/retcode. It must not reinterpret server portfolio or risk
decisions. Correlation comments need a tested bounded encoding: use a compact,
documented server correlation token plus an Agent mapping table; never silently
truncate an arbitrary global ID.

## Historical v1.0.0 reconciliation

| Historical idea | Classification | Reason |
| --- | --- | --- |
| Envelope versioning and hexagonal transport | Required, redesign needed | Keep current boundaries; define contracts from product semantics, not legacy parser compatibility. |
| Kafka / HTTPS gateway | Required, redesign needed | Ports and durable acknowledgement semantics first. |
| SQLite WAL spooler | Required, redesign needed | Historical code lacks the complete retention/recovery/atomic state design. |
| Priority aging / circuit breaker / retry | Required, redesign needed | Needs deterministic fairness, MT5 serialization and persistence interaction. |
| Idempotency | Required, redesign needed | In-memory/cache treatment cannot prove restart-safe non-duplication. |
| MachineGuid+MAC identity | Rejected as primary identity | It conflates device signal, installation, entitlement and credential. |
| ACL, mTLS, recursive redaction, JSON logs | Required, redesign needed | Security lifecycle and testable policy must precede production claims. |
| Health/readiness/heartbeat | Required, redesign needed | Use explicit readiness classes and safe telemetry. |
| Windows service host | Deferred/blocker | Session 0 evidence prevents claiming direct MT5 operation. |
| Hot JSONC reload | Deferred | Add only after immutable validated configuration and credential ownership are designed. |
| Legacy worker/parser and Python-literal payload fallback | Rejected | Broad/legacy parsing and incomplete code are unsafe for a control protocol. |

## Evidence and open decisions

The current pipeline #16 is reported as 9/9 passed with 133 local/unit tests and
the stated v0.1.3 artifact checksum. This document does not independently prove
artifact download or a live real-MT5 execution. The remaining implementation
questions are the tested Windows topology, exact schemas/limits, supported
initial command inventory and operational retention values—not the safety
invariants above.

Sources: [MQL5 Python API](https://www.mql5.com/en/docs/python_metatrader5),
[copy_rates_range semantics](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py).
