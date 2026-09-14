# v0.0.5 Error Model

| Code | Meaning |
|---|---|
| `invalid_request` | Transport/application request validation failed. |
| `authentication_failed` | Authentication failed or raised an error. |
| `authorization_failed` | Authorization policy evaluation raised an error. |
| `authorization_denied` | Authenticated principal is not permitted to execute the command. |
| `ok` | Existing command completed successfully. |
| `invalid_command` | Existing command validation failed. |
| `unsupported_schema` | Existing command schema is unsupported. |
| `unknown_command` | No handler is registered. |
| `execution_failed` | Existing handler failed unexpectedly. |

Security errors are transport-neutral. A future transport maps them to protocol-specific status representations; the application does not import transport semantics.
