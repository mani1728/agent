# Configuration — v0.0.7

Configuration is split into a transport-neutral immutable contract and an infrastructure adapter.

| Environment variable | Default | Validation |
| --- | --- | --- |
| `MT5_AGENT_HTTP_HOST` | `127.0.0.1` | non-empty string |
| `MT5_AGENT_HTTP_PORT` | `8080` | integer, `1..65535` |
| `MT5_AGENT_HTTP_MAX_REQUEST_BYTES` | `1048576` | positive integer |

`EnvironmentConfigurationProvider` is replaceable through the `ConfigurationProvider` protocol. Core does not read process environment. No credentials or secrets are stored in `AgentConfig`.

v0.0.7 intentionally does not introduce YAML/TOML/JSON configuration files, registry access, remote configuration, Vault/secrets-manager integration, or production IAM configuration.
