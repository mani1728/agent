# Error Model — v0.1.3 development

The request-time error model remains unchanged: Transport, Validation, Authentication, Authorization, Application, and Infrastructure failures remain distinct and sanitized at their established boundaries.

v0.0.8 adds process-lifecycle outcomes outside the client request model:

- invalid configuration → executable exit `2`;
- Agent startup failure → `agent_start_failed`, executable exit `1`;
- hosting/bind/serve failure → `hosting_failed`, executable exit `1`;
- Agent cleanup failure after normal serving → `agent_stop_failed`, executable exit `1`;
- normal graceful host termination → `stopped`, executable exit `0`.

Raw hosting exceptions are logged internally and are not converted into HTTP client responses.

Failure precedence is deterministic: when hosting fails and Agent cleanup also fails, the hosting failure remains primary and cleanup failure is logged. Cleanup is attempted whenever Agent startup succeeded.

## Target error model — planned

The future server protocol will retain distinct, versioned categories for
protocol, validation, authentication, authorization, unsupported capability,
busy/degraded, MT5 unavailable/initialization, broker or execution rejection,
timeout, transport, persistence, partial transfer, cancellation and internal
errors. Where safe, MT5 `last_error`/trade retcode data will be preserved as
bounded provider metadata, not collapsed into a boolean. This is a design
requirement, not current runtime behavior; see [TARGET_ARCHITECTURE.md](TARGET_ARCHITECTURE.md).

## Lifecycle error foundation (implemented in v0.1.3)

`StructuredError` provides an immutable, serializable safe error contract with a
stable code, domain, UTC timestamp, retryability and ambiguity as separate flags,
optional command/execution IDs and bounded safe details. `CommandLifecycle`
models received, validated, queued, running, terminal and ambiguous states;
expiry prevents a queued command from entering running, and cancellation never
undoes work beyond its point of no return. No scheduler, durable storage or trade
execution is introduced by these contracts.
