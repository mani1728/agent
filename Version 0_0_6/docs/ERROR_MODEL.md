# v0.0.6 Error Model

Transport and application errors remain distinct.

| Condition | Code | HTTP status |
|---|---|---:|
| malformed JSON / invalid envelope | `invalid_request` | 400 |
| invalid command | `invalid_command` | 400 |
| unsupported schema | `unsupported_schema` | 400 |
| authentication failure | `authentication_failed` | 401 |
| authorization denial | `authorization_denied` | 403 |
| unknown command | `unknown_command` | 404 |
| authorization infrastructure failure | `authorization_failed` | 500 |
| application execution failure | `execution_failed` | 500 |
| unexpected application boundary exception | `application_error` | 500 |
| response serialization failure | `transport_error` | 500 |

Raw framework exceptions and tracebacks are never returned to the HTTP client.
