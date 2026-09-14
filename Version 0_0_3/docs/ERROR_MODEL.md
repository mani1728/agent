# Error Model

The application boundary converts expected command failures into deterministic `CommandResult.code` values.

| Code | Meaning |
|---|---|
| `invalid_command` | Command envelope violates contract validation. |
| `unsupported_schema` | Command schema version is not supported. |
| `unknown_command` | No handler is registered for the command type. |
| `execution_failed` | Registered handler raised an unexpected exception. |
| `ok` | Command completed successfully. |

Infrastructure-specific failures remain outside the command contract. They are not exposed as HTTP/Kafka/socket-specific errors.
