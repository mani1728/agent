# Contracts — v0.0.7

v0.0.7 preserves all v0.0.6 command, transport, security, observability, runtime, and MT5 contracts and adds startup configuration contracts.

## AgentConfig

Immutable top-level startup configuration. It currently contains `HTTPTransportConfig` only; it is intentionally narrow and represents configuration actually consumed by this version.

## HTTPTransportConfig

Immutable fields: `host`, `port`, and `max_request_bytes`. Validation requires a non-empty host, TCP port in `1..65535`, and positive request-body limit.

## ConfigurationProvider

Protocol:

```python
def load(self) -> AgentConfig: ...
```

The contract does not prescribe environment variables, files, registries, secrets managers, or remote configuration.

## ConfigurationError

Deterministic startup contract violation. It is not an HTTP/client error and must not leak through request processing.
