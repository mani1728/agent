# Command Contract

## Envelope

`Command` is an immutable application-level envelope. It has no dependency on HTTP, Kafka, sockets, databases or external SDKs.

| Field | Semantics |
|---|---|
| `command_id` | Unique command identity supplied by the caller. |
| `command_type` | Stable application command name. |
| `schema_version` | Version of the command envelope/schema. v0.0.3 supports `1`. |
| `correlation_id` | Identifier used to correlate a command with related logs/results. |
| `timestamp` | ISO-8601 command creation timestamp. |
| `payload` | Transport-neutral mapping containing command-specific data. |

## Validation

A command is rejected before dispatch when identity fields are empty, timestamp is not ISO-8601, payload is not a mapping, or schema version is unsupported.

## Result

`CommandResult` contains `command_id`, `correlation_id`, `success`, `code`, `message` and optional `data`.

## Idempotency

`command_id` establishes identity. Persistent duplicate detection is not implemented in this version because persistence is out of scope.
