# Durable SQLite Foundation — v0.1.3

**Implemented:** `SQLiteDurableCommandState` is an infrastructure adapter behind
`DurableCommandStatePort`. It owns one local SQLite connection, enables WAL,
foreign keys and a bounded 5-second busy timeout, and applies schema version 1
using `PRAGMA user_version`. Schema v1 was migrated in order to v2 (durable
`agent_execution_id`, optional MT5 correlation fields and reconciliation state),
then v3 (durable outbox). Existing v1 command rows are retained; no reset or
destructive migration is performed. The initial `commands` table persists server command
identity, command identifier/version, lifecycle state, UTC timestamps, requested
priority and point-of-no-return marker.

Insertion is transactional and the primary key rejects duplicates. Load,
persisted transition and non-terminal recovery-candidate queries are available.
**Implemented:** `server_command_id` is the unique delivery identity and maps to
one stable `agent_execution_id`. Optional correlation records MT5 request, order,
and position tickets. A command crossing point of no return can become terminal
`ambiguous`; it is excluded from recovery candidates until reconciliation records
`proven_executed`, `proven_not_executed`, or `still_ambiguous`. This never authorizes replay.

The v3 outbox retains JSON-canonical outbound messages until explicit acknowledgement.
Sending merely records an attempt; restart may retransmit unacknowledged records.
Ordering is deterministic per topic. No retention cleanup deletes unacknowledged data.

## Historical transfer checkpoint — schema v4

**Implemented:** v4 adds durable per-transfer partition checkpoints. Historical records are partitioned before adapter retrieval, serialized into deterministic SHA-256 checked chunks, and enqueued through the existing outbox. Restart resumes only after the saved partition; large dataset/real-MT5 scale validation remains **PENDING PRODUCTION VALIDATION**.
