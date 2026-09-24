# Security lifecycle — Work Item #12

**IMPLEMENTED foundation:** Agent and installation identities are non-secret UUIDs.
Credential material is represented only by a SHA-256 fingerprint in the local authority;
unknown, rotated, and revoked credentials fail closed. Authorization reuses the existing
command/capability model: a READ permission cannot authorize execution.

**PENDING PRODUCTION VALIDATION:** durable secret storage, enrollment transport, certificate
issuance, mTLS, and production credential rotation/recovery. No trust anchor is remotely mutable.
