# v0.0.4 Error Model

## Contract Layer

`TransportValidationError` represents an invalid transport-neutral request envelope or execution context. The application boundary converts it to:

```text
invalid_request
```

The existing command contract retains:

```text
invalid_command
unsupported_schema
```

## Application Layer

The dispatcher retains:

```text
unknown_command
execution_failed
```

Successful execution remains:

```text
ok
```

## Boundary Rule

Concrete transport exceptions and protocol-specific error models must not cross into Core/Application. A future adapter is responsible for translating its protocol into `TransportRequest` and translating `TransportResponse` back into that protocol.
