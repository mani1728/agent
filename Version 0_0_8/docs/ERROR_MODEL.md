# Error Model — v0.0.8

The request-time error model remains unchanged: Transport, Validation, Authentication, Authorization, Application, and Infrastructure failures remain distinct and sanitized at their established boundaries.

v0.0.8 adds process-lifecycle outcomes outside the client request model:

- invalid configuration → executable exit `2`;
- Agent startup failure → `agent_start_failed`, executable exit `1`;
- hosting/bind/serve failure → `hosting_failed`, executable exit `1`;
- Agent cleanup failure after normal serving → `agent_stop_failed`, executable exit `1`;
- normal graceful host termination → `stopped`, executable exit `0`.

Raw hosting exceptions are logged internally and are not converted into HTTP client responses.

Failure precedence is deterministic: when hosting fails and Agent cleanup also fails, the hosting failure remains primary and cleanup failure is logged. Cleanup is attempted whenever Agent startup succeeded.
