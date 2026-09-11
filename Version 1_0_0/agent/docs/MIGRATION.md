# Migration status

## Phase 3 continuation — Kafka commit semantics and transport boundary

### Observed pre-change behavior

- `KafkaListener` constructed a consumer with `kafka.enable_auto_commit`,
  whose default is `true`.
- It parsed command payloads into `CommandEnvelope` objects but did not retain
  the consumed Kafka record for a later commit.
- `KafkaTransport.ack_command()` only logged an acknowledgement; it did not
  call Kafka.
- The legacy protocol uses the Kafka message key as the target class and the
  `cmd.<client_id>.p0|p1|p2` topic suffix as command priority.  The listener
  did not pass either source into `CommandEnvelope` construction.

### Implemented compatibility behavior

- The default remains Kafka auto-commit.  No configuration value was changed.
  This preserves the active legacy delivery behavior.
- With an explicitly configured application-managed policy (`manual` or
  `after_response`, and `enable_auto_commit=false`), `KafkaTransport` retains
  a commit tracker and `ack_command()` calls synchronous
  `Consumer.commit(message=...)` only after the tracker reaches
  `RESPONSE_SENT`.
- A Kafka record containing a command list is committed only after every
  command generated from that record has been acknowledged.  This prevents an
  earlier response from committing offsets for unacknowledged sibling commands.
- No automatic change to manual offsets is enabled before SQLite spooler
  wiring.  Phase 6 must make a response durable before using the
  application-managed mode in production.

### Remaining boundary

`AgentWorker` still does not call `send_response()` and `ack_command()`; that
runtime wiring belongs to the subsequent AgentWorker lifecycle phase.  Do not
set `kafka.enable_auto_commit=false` in a deployed configuration until the
spooler phase provides durable recovery.

## Phase 5 — AgentWorker and opt-in entry-point wiring

- `AgentWorker` now owns the transport-agnostic sequence
  `poll -> execute -> send_response -> ack_command`.
- A response that is rejected or raises during publication is not acknowledged.
- `agent.main` selects this path only when `app.use_agent_worker=true`; the
  default remains the legacy `KafkaListener` thread.
- The worker is started in a daemon thread and is stopped before `ClientAuth`
  during the existing main shutdown path.  The final bounded, multi-stage
  shutdown protocol and spooler-backed acknowledgement remain later phases.
