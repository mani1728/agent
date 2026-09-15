# Release Notes — v0.0.7

## Agent Configuration & Composition Root Foundation

v0.0.7 formalizes startup configuration and dependency assembly. It adds immutable configuration contracts, a replaceable configuration-provider protocol, an environment adapter, and a single composition root that wires MT5, security, observability, application, and HTTP components.

The HTTP request-body limit is now configuration-driven while HTTP details remain outside Core. Invalid startup configuration fails deterministically before request handling.

No trading, order execution, persistence, AI/LLM, production IAM, secrets management, TLS/mTLS, remote configuration, or new transport technology is introduced.

Planned artifact: `MT5Agent-v0.0.7.exe`.

Status: **pre-merge review**. CI result, final artifact SHA-256, merge commit, tag, release, and artifact verification must be recorded only after those events actually occur.
