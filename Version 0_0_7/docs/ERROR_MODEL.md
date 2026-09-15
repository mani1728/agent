# Error Model — v0.0.7

Request-time categories remain distinct: Transport, Validation, Authentication, Authorization, Application, and Infrastructure failures. Raw internal/framework exceptions must never be returned to an external client.

## Startup configuration failure

`ConfigurationError` is a startup/infrastructure failure. It occurs before the application accepts requests and therefore does not add a new external request error category.

Invalid environment integer syntax, invalid host, out-of-range port, or non-positive request limit causes deterministic startup rejection. The executable uses exit code `2` for invalid startup configuration.

The existing HTTP mapping, security error mapping, application exception sanitization, response serialization protection, and observer failure isolation remain unchanged.
