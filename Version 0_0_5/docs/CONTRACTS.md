# v0.0.5 Contracts

## SecurityContext

Immutable authenticated principal context:

- `principal_id`
- `authentication_method`
- immutable `permissions`
- immutable `metadata`

## AuthenticationResult

Represents authentication outcome without transport-specific semantics.

- `success`
- optional `SecurityContext`
- deterministic `code`
- `message`

## AuthorizationDecision

Represents policy outcome:

- `allowed`
- deterministic `code`
- `message`

## Ports

```python
Authenticator.authenticate(request) -> AuthenticationResult
Authorizer.authorize(context, command) -> AuthorizationDecision
ObservabilityPort.record(event) -> None
```

## ExecutionEvent

Immutable telemetry contract containing event/request/correlation/command identity, UTC timestamp, event type, outcome and immutable metadata.

## Development adapters

`AllowAllAuthenticator`, `AllowAllAuthorizer`, and `NullObservability` exist only as explicit defaults for local execution and tests. They do not provide production security.
