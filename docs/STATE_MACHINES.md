# Target State Machines

**Status:** decided behavior models; not runtime implementation. Every transition
must be durable/auditable where it changes execution safety.

| Machine | States and safety transition |
| --- | --- |
| Agent | `STARTING → RUNNING → QUIESCING → QUIESCED → RESUMING → RUNNING`; `DEGRADED` may restrict readiness; `STOPPING → STOPPED`. Quiesced retains authenticated control/heartbeat. |
| Command | `RECEIVED → VALIDATED → AUTHORIZED → ACCEPTED → EXECUTING → RESULT_OBTAINED → RESPONSE_PERSISTED → TRANSMITTED → ACKNOWLEDGED`; terminal alternatives: rejected, expired, cancelled, ambiguous. |
| Trade | `PREPARED → POINT_OF_NO_RETURN → SUBMITTED → CONFIRMED` or `AMBIGUOUS → RECONCILING → CONFIRMED/NOT_EXECUTED`. Ambiguous never automatically re-enters submitted. |
| Bulk job | `QUEUED → RUNNING_PARTITION → CHECKPOINTED/PAUSED → RUNNING_PARTITION → COMPLETED`; cancellation/preemption happens only at safe partition boundaries. |
| MT5 Runtime | `UNAVAILABLE → DISCOVERED → INITIALIZING → READY → DEGRADED/FAILED → SHUTTING_DOWN`. Direct Session 0 use remains prohibited until ADR-001 succeeds. |
| Connectivity | `CONNECTED → DISCONNECTED → OUTBOXING → RESYNCING → CONNECTED`; reconnect reconciles acknowledgements and does not invent new work. |
| Configuration | `RECEIVED → AUTHORIZED → VALIDATED → STAGED → APPLIED → HEALTHY/COMMITTED`; unhealthy becomes `ROLLED_BACK` to last-known-good. |
| Update | `OFFERED → VERIFIED → STAGED → ACTIVATED → HEALTHY/COMMITTED`; failure rolls back. Update remains future work. |
