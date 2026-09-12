<div align="center">

<h1>🏛️ Enterprise MetaTrader 5 (MT5) AI-Driven Trading Agent</h1>

<p><strong>A mission-critical, transport-agnostic execution engine bridging algorithmic/AI trading systems with MetaTrader 5 terminals.</strong></p>

<p>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg" alt="Python Version"></a>
  <a href="#-architecture-overview"><img src="https://img.shields.io/badge/Architecture-Hexagonal%20%2F%20Clean-emerald.svg" alt="Architecture"></a>
  <a href="#-transport-layer"><img src="https://img.shields.io/badge/Transport-Kafka%20%7C%20mTLS%20Gateway-orange.svg" alt="Transport"></a>
  <a href="#-persistence--resilience-engine"><img src="https://img.shields.io/badge/Reliability-SQLite%20WAL%20Spooler%20%7C%20Circuit%20Breaker-purple.svg" alt="Reliability"></a>
  <a href="#-security--governance"><img src="https://img.shields.io/badge/Security-mTLS%20%7C%20ACL%20%7C%20Deterministic%20Identity-red.svg" alt="Security"></a>
  <a href="#-license--compliance"><img src="https://img.shields.io/badge/License-Proprietary-lightgrey.svg" alt="License"></a>
</p>

</div>

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture Overview](#-architecture-overview)
- [Project Structure](#-project-structure)
- [Security & Governance](#-security--governance)
- [Persistence & Resilience Engine](#-persistence--resilience-engine)
- [Configuration Specification](#️-configuration-specification)
- [Installation & Deployment](#-installation--deployment)
- [Command & Response Lifecycle](#-command--response-lifecycle)
- [Testing & Verification](#-testing--verification)
- [Telemetry & Health Endpoints](#️-telemetry--health-endpoints)
- [License & Compliance](#-license--compliance)
---

## 📌 Overview

The **Enterprise MT5 Trading Agent** is a mission-critical, resilient, and transport-agnostic microservice designed to bridge algorithmic and AI-driven trading engines with MetaTrader 5 terminals.

Engineered under strict **Clean / Hexagonal Architecture** principles, the agent provides:

- **Robust execution** of trading commands against MT5 terminals
- **Deterministic machine identity** backed by hardware fingerprinting
- **Military-grade log redaction** to prevent credential leakage
- **Durable message spooling** with SQLite WAL journaling
- **Multi-transport connectivity** via Apache Kafka and HTTPS/mTLS Gateway

The system is designed for **24/7 unattended operation** in regulated environments where reliability, auditability, and failure containment are non-negotiable.

---

## ✨ Key Features

| Domain | Capability |
| :--- | :--- |
| **Execution** | Deterministic command envelope versioning (V1) with priority scheduling and aging |
| **Transport** | Pluggable Kafka (SASL_SSL) & HTTPS/mTLS Gateway transports via `ITransportClient` |
| **Reliability** | SQLite WAL spooler with **At-Least-Once Delivery**, circuit breaker, and idempotency guard |
| **Security** | Deterministic hardware fingerprint, deny-by-default ACL, deep recursive log redaction |
| **Observability** | Structured JSON logging, liveness/readiness probes, periodic heartbeats |
| **Operations** | Windows Service host, graceful shutdown, hot-reloading configuration |
| **Architecture** | Hexagonal boundaries isolating domain logic from adapters, transport, and persistence |

---

## 🏗️ Architecture Overview

The system isolates domain and execution logic from transport, persistence, and external broker drivers.

```text
                                 ┌─────────────────────────────────────────┐
                                 │   External Control Plane / AI Engine    │
                                 └────────────────────┬────────────────────┘
                                                      │ (mTLS / SASL)
                                                      ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                              TRANSPORT LAYER                                            │
 │   ┌──────────────────────────────────────────────────┐   ┌──────────────────────────────────────────┐   │
 │   │ KafkaTransport (Listener + Responder)            │   │ GatewayHttpTransport (REST / Polling)    │   │
 │   │ - Dynamic Topic Injection (cmd.{id}.p0/p1/p2)    │   │ - Strict TLS/mTLS Verification           │   │
 │   │ - Commit Policy: AUTO / MANUAL / AFTER_RESPONSE  │   │ - Idempotent-Aware Retry & Exponential   │   │
 │   └─────────────────────────┬────────────────────────┘   └────────────────────┬─────────────────────┘   │
 └─────────────────────────────┼─────────────────────────────────────────────────┼─────────────────────────┘
                               │                                                 │
                               └───────────────────────┬─────────────────────────┘
                                                       ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                              AGENT CORE                                                 │
 │   ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐   │
 │   │ AgentWorker (Lifecycle: CREATED ➔ RUNNING ➔ STOPPING ➔ STOPPED)                                │   │
 │   │ - Pulls from ITransportClient                                                                   │   │
 │   │ - Enforces Command Envelope Versioning (V1)                                                     │   │
 │   └─────────────────────────────────────────┬───────────────────────────────────────────────────────┘   │
 │                                             │                                                           │
 │         ┌───────────────────────────────────┼───────────────────────────────────┐                       │
 │         ▼                                   ▼                                   ▼                       │
 │ ┌────────────────────────┐        ┌─────────────────────────┐        ┌────────────────────────┐         │
 │ │   CommandAuthorizer    │        │    PriorityExecutor     │        │   IdempotencyManager   │         │
 │ │ (Deny-by-Default ACL)  │        │ (Task Priority + Aging) │        │ (Deduplication Lock)   │         │
 │ └──────────────┬─────────┘        └────────────┬────────────┘        └───────────┬────────────┘         │
 │                │                               │                                 │                      │
 │                └───────────────────────┬───────┴─────────────────────────────────┘                      │
 │                                        ▼                                                                │
 │                           ┌───────────────────────────┐                                                 │
 │                           │      CommandExecutor      │                                                 │
 │                           │ (Dispatches to Adapters)  │                                                 │
 │                           └────────────┬──────────────┘                                                 │
 └────────────────────────────────────────┼────────────────────────────────────────────────────────────────┘
                                          │
            ┌─────────────────────────────┴─────────────────────────────┐
            ▼                                                           ▼
 ┌──────────────────────────────────────┐                    ┌──────────────────────────────────────┐
 │          ADAPTERS & RUNTIME          │                    │       PERSISTENCE & RELIABILITY      │
 │ ┌──────────────────────────────────┐ │                    │ ┌──────────────────────────────────┐ │
 │ │ Mt5Adapter (MetaTrader 5 Native) │ │                    │ │ SQLiteSpooler (WAL Mode)         │ │
 │ ├──────────────────────────────────┤ │                    │ ├──────────────────────────────────┤ │
 │ │ SystemAdapter (OS / Host Specs)  │ │                    │ │ CircuitBreaker (Fail-Fast Gate)  │ │
 │ ├──────────────────────────────────┤ │                    │ ├──────────────────────────────────┤ │
 │ │ ResultBuilder (Standard Envelopes)││                    │ │ MigrationRunner (SHA-256 Ver.)   │ │
 │ └──────────────────────────────────┘ │                    │ └──────────────────────────────────┘ │
 └──────────────────────────────────────┘                    └──────────────────────────────────────┘
```

---

## 📂 Project Structure

```text
agent/
├── adapters/                 # Boundaries to external runtimes & terminals
│   ├── mt5_adapter.py        # MT5 native API wrapper & trading primitives
│   └── system_adapter.py     # OS metrics, CPU, RAM & host introspection
├── contracts/                # Strongly-typed schemas and envelope models
│   ├── command.py            # CommandEnvelope & Action payloads
│   ├── response.py           # ResponseEnvelope & Mt5ResultV1
│   ├── heartbeat.py          # Heartbeat contracts & status flags
│   └── schemas.py            # JSON schema validation & version tracking
├── core/                     # Domain orchestration & execution engine
│   ├── worker.py             # AgentWorker pipeline loop
│   ├── command_executor.py   # Command routing & authorization gate
│   ├── dispatcher.py         # Subsystem action dispatching
│   ├── meta_trader_manager.py# High-level terminal state & account manager
│   ├── result_builder.py     # Unified response normalizer
│   └── mt5_utils.py          # Numeric precision & symbol normalizers
├── infrastructure/           # Low-level cross-cutting components
│   ├── config_manager.py     # Hot-reloading JSONC configuration engine
│   ├── config_logging.py     # JSON logging with automated redaction filters
│   ├── priority_executor.py  # Thread pool with priority queues and aging
│   ├── thread_manager.py     # Structured concurrency & worker threads
│   ├── lifecycle.py          # Signal handling & graceful shutdown hooks
│   └── platform.py           # OS detection & abstraction
├── persistence/              # Reliable local storage & state management
│   ├── sqlite_spooler.py     # SQLite spooler with WAL journal mode
│   ├── spool_repository.py   # Spool database abstraction layer
│   └── migrations.py         # Versioned schema migrations (SHA-256 protected)
├── reliability/              # Resilience patterns & fault tolerance
│   ├── circuit_breaker.py    # State-machine circuit breaker (CLOSED/OPEN/HALF_OPEN)
│   ├── idempotency.py        # Deduplication cache for incoming commands
│   ├── retry.py              # RetryExecutor with policy binding
│   └── backoff.py            # Exponential backoff with bounded jitter
├── security/                 # Identity, credentials, and access control
│   ├── client_auth.py        # Hardware fingerprinting (MachineGuid + MAC)
│   ├── certificate_manager.py# mTLS validation & SSLContext assembly
│   ├── command_authorizer.py # Deny-by-default capability ACL
│   ├── redaction.py          # Deep recursive log scrubbing for secrets
│   └── secret_provider.py    # Multi-source secret provider chain
├── transport/                # Communication drivers (Kafka / HTTP)
│   ├── base.py               # ITransportClient abstraction
│   ├── factory.py            # Transport runtime factory
│   ├── errors.py             # Transport error hierarchy
│   ├── gateway/              # HTTP/REST mTLS transport implementation
│   │   ├── gateway_adapter.py# GatewayHttpTransport client
│   │   ├── http_client.py    # Requests session wrapper with mTLS
│   │   ├── retry_policy.py   # HTTP status-aware & idempotency-aware retries
│   │   └── endpoints.py      # Route builders & URL normalization
│   └── kafka/                # High-throughput Kafka transport implementation
│       ├── kafka_transport.py# KafkaTransport client wrapper
│       ├── listener.py       # High-throughput consumer & topic multiplexer
│       ├── responder.py      # Chunked response publisher (acks=all)
│       ├── commit_policy.py  # Acknowledgment & Offset commit tracker
│       └── serializers.py    # Safe JSON encoding / envelope parsing
├── health/                   # Observability & runtime diagnostics
│   ├── health_checker.py     # Liveness evaluation
│   ├── readiness.py          # Readiness verification (MT5 & Transport ready)
│   └── metrics.py            # Metric collectors & runtime counters
├── service_host.py           # Production Windows Service runtime wrapper
├── main.py                   # Service bootstrapper & wiring entry point
├── __main__.py               # `python -m agent` CLI invocation hook
└── requirements.txt          # Frozen dependencies with phase migration tags
```

---

## 🔒 Security & Governance

### 1. Deterministic Agent Fingerprint — `client_auth.py`

Computes an immutable Machine ID derived from:

- `Windows MachineGuid`
- `Primary MAC Address`
- `Node Name`

Hashed with `SHA-256` and stored atomically via temporary file swaps with explicit `fsync` barriers.

### 2. Deny-by-Default Command ACL — `command_authorizer.py`

Every incoming envelope is validated against a strict allowlist. Unauthorized actions fail fast with `COMMAND_UNAUTHORIZED` **before** touching the terminal.

### 3. Data Redaction & Sanitization — `redaction.py`

- Deep recursive scrubbing across dictionaries, lists, and embedded JSON strings
- Intercepts standard logging handlers to prevent credential/token leaks in console and file outputs

### 4. Mutual TLS (mTLS)

Hardened `SSLContext` requiring paired private keys and CA bundles. Disabling certificate verification (`verify=False`) is strictly rejected at the schema level.

---

## ⚡ Persistence & Resilience Engine

### SQLite WAL Spooler — `sqlite_spooler.py`

Guarantees **At-Least-Once Delivery** during broker connectivity loss or ungraceful shutdown.

```text
[Received] ➔ [PENDING] ➔ [PROCESSING] ➔ [ACKNOWLEDGED]
                             └──(Fail)➔ [RETRY_SCHEDULED] ➔ [DEAD]
```

### Circuit Breaker — `circuit_breaker.py`

Protects MT5 terminals from cascading failures during network degradation or broker freezes. Transitions across `CLOSED`, `OPEN`, and `HALF_OPEN` states.

### Idempotency Guard — `idempotency.py`

Prevents duplicate execution of non-idempotent trading operations (e.g., market orders) caused by network retries.

---

## ⚙️ Configuration Specification

The agent reads from a hot-reloading `config.jsonc` (or `config.jsonc`).

```json
{
  "app": {
    "use_agent_worker": true,
    "worker_poll_timeout_sec": 1.0,
    "log_level": "INFO"
  },
  "transport": {
    "type": "kafka"
  },
  "kafka": {
    "bootstrap_servers": "kafka-cluster.bank.local:9092",
    "security_protocol": "SASL_SSL",
    "sasl_mechanism": "PLAIN",
    "sasl_username": "mt5_agent_prod",
    "sasl_password": "vault:secret/data/mt5#password",
    "enable_auto_commit": false,
    "commit_policy": "AFTER_RESPONSE",
    "topics": {
      "commands": "cmd.agent-xauusd.p0",
      "responses": "rsp.agent-xauusd",
      "heartbeats": "hb.agents"
    }
  },
  "gateway": {
    "base_url": "https://trading-gateway.bank.local/v1",
    "client_cert": "certs/agent.crt",
    "client_key": "certs/agent.key",
    "ca_bundle": "certs/ca-bundle.crt",
    "timeout_sec": 5.0
  },
  "mt5": {
    "path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
    "server": "Broker-Demo",
    "login": 100200300,
    "password": "env:MT5_TERMINAL_PASSWORD",
    "timeout_ms": 60000
  },
  "persistence": {
    "spool_db_path": "data/spool.db",
    "max_retries": 5
  }
}
```

---

## 🚀 Installation & Deployment

### 1. Prerequisites

| Component | Requirement |
| :--- | :--- |
| **Python** | 3.10, 3.11, or 3.12 (64-bit) |
| **MetaTrader 5 Terminal** | Build 3800+ installed on host |
| **Operating System** | Windows 10/11, Windows Server 2019/2022 (native MT5), or Linux via Wine / K8s sidecar |

### 2. Environment Setup

```powershell
# Clone the repository
git clone https://github.com/your-org/mt5-trading-agent.git
cd mt5-trading-agent

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install production dependencies
pip install -r requirements.txt
```

### 3. Running as a Console Application

```powershell
# Run using the modular execution entry point
python -m agent

# Alternatively, run via direct bootstrap
python main.py
```

### 4. Running as a Windows Service (Production)

```powershell
# Install the Windows Service
python service_host.py install

# Configure service to auto-start
Set-Service -Name "MT5Agent" -StartupType Automatic

# Start the service
python service_host.py start

# Query status
Get-Service -Name "MT5Agent"
```

---

## 🔄 Command & Response Lifecycle

```text
1. [Broker/Engine] ──> Kafka Topic (cmd.{agent_id}.p0)
                             │
2. [KafkaListener] ──> Deserialize JSON / Validate Envelope (CommandEnvelopeV1)
                             │
3. [AgentWorker]   ──> Verify ACL (CommandAuthorizer)
                             │
4. [Idempotency]   ──> Check Executed Cache (Prevent duplicates)
                             │
5. [CommandExec]   ──> Execute via Mt5Adapter (Atomic MT5 API call)
                             │
6. [ResultBuilder] ──> Format ResponseEnvelope (Mt5ResultV1)
                             │
7. [KafkaResponder]──> Publish to reply topic (acks=all)
                             │
8. [CommitPolicy]  ──> Mark Ack ➔ Commit Kafka Offset (AFTER_RESPONSE)
```

---

## 🧪 Testing & Verification

```powershell
# Run unit tests
pytest tests/unit -v

# Run integration tests (requires live/demo MT5 instance)
pytest tests/integration -m "mt5"

# Run security & redaction verification suite
pytest tests/unit/test_redaction.py -v
```

---

## 🛡️ Telemetry & Health Endpoints

The agent exposes internal health semantics consumed by container orchestrators and monitoring daemons:

| Probe | Check Mechanism | Criteria |
| :--- | :--- | :--- |
| **Liveness** | `HealthChecker.check_health()` | Main loop alive, thread responsiveness, spooler I/O operational |
| **Readiness** | `ReadinessChecker.check_readiness()` | Transport connected, MT5 terminal initialized & logged in |
| **Heartbeat** | `HeartbeatManager` | Periodic payload containing CPU/RAM, active orders, latency |

---

## 📄 License & Compliance

**Confidential & Proprietary.**

Developed for secure, automated trading infrastructure. All rights reserved. Unauthorized distribution, reproduction, or use of this software, in whole or in part, is strictly prohibited without prior written consent from the copyright holder.

---

<div align="center">

**Built for resilience. Engineered for trust.**

</div>

