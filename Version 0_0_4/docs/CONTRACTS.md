# v0.0.4 Contracts

## ExecutionContext

Immutable request-scoped context:

| Field | Meaning |
|---|---|
| `request_id` | Identity of one ingress request. |
| `correlation_id` | Workflow/request correlation identifier. |
| `metadata` | Transport-neutral immutable metadata. |

## TransportRequest

```text
TransportRequest
├── context: ExecutionContext
└── command: Command
```

The context and command `correlation_id` values must match.

## TransportResponse

```text
TransportResponse
├── request_id
├── correlation_id
├── command_id
├── success
├── code
├── message
└── data
```

The response mirrors application outcome data without introducing HTTP, Kafka, WebSocket, or socket semantics.

## ApplicationPort

Future transport adapters target:

```python
handle(request: TransportRequest) -> TransportResponse
```

The application owns the implementation; transport implementations remain outside the Core/Application dependency direction.

## Validation Layers

```text
TransportRequest validation
          ↓
Command validation
          ↓
Schema validation
          ↓
Handler execution
```

This version does not introduce authentication, authorization, persistence, retries, or durable idempotency.
