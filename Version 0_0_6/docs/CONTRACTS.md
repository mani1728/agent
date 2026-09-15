# v0.0.6 Contracts

## TransportRequest

Immutable envelope containing `ExecutionContext` and a transport-neutral `Command`.

## ExecutionContext

Immutable propagation context containing:

- `request_id`
- `correlation_id`
- metadata

## TransportResponse

Immutable application egress containing:

- `request_id`
- `correlation_id`
- `command_id`
- `success`
- deterministic `code`
- `message`
- optional `data`

## HTTP representation

The HTTP adapter maps one JSON object to `TransportRequest` and one `TransportResponse` to JSON. HTTP types do not cross the `ApplicationPort` boundary.
