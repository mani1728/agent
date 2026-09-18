# Transport — v0.0.8

The v0.0.6 HTTP request contract remains unchanged: `POST /command` translates HTTP/JSON into `TransportRequest`, delegates to `ApplicationPort`, and maps `TransportResponse` back to deterministic HTTP responses.

v0.0.8 separates request translation from server lifecycle ownership:

```text
HTTPServerHost [Infrastructure]
        ↓ owns lifecycle of
ThreadingHTTPServer
        ↓ delegates request handling to
HTTPTransportAdapter
        ↓
ApplicationPort
```

`HTTPTransportAdapter` remains responsible for protocol translation, request-size enforcement, endpoint behavior, response serialization, and deterministic HTTP mapping. `HTTPServerHost` owns blocking `serve_forever()`, graceful `shutdown()`, and socket closure.

No HTTP type is introduced into `HostingPort`, ApplicationHost, Core, or domain contracts. Security ordering and identity propagation remain unchanged.
