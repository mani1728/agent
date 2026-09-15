# Architecture — v0.0.7

## Purpose

v0.0.7 introduces a configuration and composition boundary without changing Core dependency direction.

```text
Process Environment
      ↓
EnvironmentConfigurationProvider   [Infrastructure]
      ↓
AgentConfig                         [Contract]
      ↓
compose_agent                       [Composition Root]
  ├── MT5Port → MT5Adapter
  ├── AuthenticationPort
  ├── AuthorizationPort
  └── ObservabilityPort
      ↓
ApplicationBoundary
      ↓
HTTPTransportAdapter
```

The composition root is the only assembly point for concrete dependencies. Core remains unaware of environment variables, HTTP server details, security infrastructure, observability backends, packaging, and the `MetaTrader5` package.

Security order remains `Validation → Authentication → Authorization → Dispatch`. Observability remains injectable and best-effort. `request_id`, `correlation_id`, and `command_id` propagation is unchanged.

Configuration parsing is an infrastructure concern. Invalid startup configuration fails before request acceptance and does not enter the request error model.
