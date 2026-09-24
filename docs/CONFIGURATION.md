# Configuration — v0.0.7

Configuration is split into a transport-neutral immutable contract and an infrastructure adapter.

| Environment variable | Default | Validation |
| --- | --- | --- |
| `MT5_AGENT_HTTP_HOST` | `127.0.0.1` | non-empty string |
| `MT5_AGENT_HTTP_PORT` | `8080` | integer, `1..65535` |
| `MT5_AGENT_HTTP_MAX_REQUEST_BYTES` | `1048576` | positive integer |

`EnvironmentConfigurationProvider` is replaceable through the `ConfigurationProvider` protocol. Core does not read process environment. No credentials or secrets are stored in `AgentConfig`.

v0.0.7 intentionally does not introduce YAML/TOML/JSON configuration files, registry access, remote configuration, Vault/secrets-manager integration, or production IAM configuration.

## Remote configuration — Work Item #11

**IMPLEMENTED foundation:** versioned candidates are policy-validated before atomic apply;
`LOCAL_ONLY` values (including trust roots) reject remote mutation, while `WITH_LIMITS`
values retain local bounds. A failed health check leaves the known-good revision active;
rollback restores the prior revision. Durable remote-config storage and authenticated transport
remain **PENDING PRODUCTION VALIDATION**.

## Logging (v0.1.2)

`MT5_AGENT_LOG_LEVEL` accepts DEBUG, INFO (default), WARNING and ERROR,
case-insensitively. Invalid levels produce the existing configuration error exit
2 in normal mode; diagnostics report not-ready with exit 1.
`MT5_AGENT_LOG_FILE` optionally appends UTF-8 logs to an existing parent directory.
Opening/writing a log sink is best-effort and does not fail the runtime.
Inspection-only diagnostics never create the file.
