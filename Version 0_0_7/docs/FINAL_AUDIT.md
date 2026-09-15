# Final Audit — v0.0.7

## Final published state

Scope is limited to **Agent Configuration & Composition Root Foundation**. Trading and all declared non-goals remain absent.

### Architecture

- Core does not read environment variables.
- Core remains independent of HTTP implementation and `MetaTrader5` package imports.
- Configuration parsing resides in infrastructure.
- Concrete dependency assembly resides in the composition root.
- Security order remains Validation → Authentication → Authorization → Dispatch.
- Observability remains injectable and best-effort.
- Request/correlation/command identity contracts are unchanged.
- Startup configuration failures remain outside the client request error model.

### CI / packaging evidence

Final pre-merge head `bc0b3aae0a95ab87ed5c7ac1bde13d4c3a03024f` passed the v0.0.7 Windows workflow: tests, build, executable verification, unavailable-terminal smoke test, invalid-configuration smoke test, checksum generation, and artifact upload.

Published release evidence:

- PR: `#39` — merged
- merge commit: `a93812eee78692692982b831bc2a920ab6d104f6`
- finalized main/tag commit: `487db94c8a50f0db6c65d1e9f8fbcbd12aefa81d`
- tag: `v0.0.7`
- GitHub Release: published
- file: `MT5Agent-v0.0.7.exe`
- canonical executable SHA-256: `38c17331fd3426c18f1c5774cafcdb4186f6810f529b9e1e548c91cf2db275e0`
- final GitHub Actions artifact digest: `sha256:d26b0432548a0f44962a75ff8288926b107f0cb0dc27d31c8a0e72f48857e46e`

The canonical executable checksum was independently recomputed from the final artifact and matched its generated `sha256.txt`.

### Historical checksum note

PR #39's description contains checksum/digest values from an earlier CI artifact. Those values are retained as historical PR evidence and are not rewritten. They are not the canonical checksum of the published release asset. The canonical published executable SHA-256 is the value recorded above.

### Closure

v0.0.7 is **PUBLISHED AND CLOSED**. Later development must not move `v0.0.7`, rewrite its history, or replace its published release asset.
