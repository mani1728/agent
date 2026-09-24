# Durable SQLite Foundation — v0.1.3

**Implemented:** `SQLiteDurableCommandState` is an infrastructure adapter behind
`DurableCommandStatePort`. It owns one local SQLite connection, enables WAL,
foreign keys and a bounded 5-second busy timeout, and applies schema version 1
using `PRAGMA user_version`. The initial `commands` table persists server command
identity, command identifier/version, lifecycle state, UTC timestamps, requested
priority and point-of-no-return marker.

Insertion is transactional and the primary key rejects duplicates. Load,
persisted transition and non-terminal recovery-candidate queries are available.
**Deferred:** outbox, acknowledgements, complete idempotency/reconciliation,
retention cleanup and execution replay. No cleanup exists that could weaken future
duplicate-trade protection.
