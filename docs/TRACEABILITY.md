# Product-to-Delivery Traceability

| Product requirement | Architecture / ADR | Roadmap | GitLab issue family | Test evidence |
| --- | --- | --- | --- | --- |
| One safe unattended MT5 runtime | ADR-001 (provisional) | B, H | #1, #14 | Session 1 direct-worker probe passed; unattended-launch experiment pending |
| Explicit/versioned allowlisted commands | Target Architecture | A | #2, #3 | Schema/negative compatibility |
| No duplicate or expired trade | Target Architecture | C, G | #3, #4, #5, #14 | Crash/retry/TTL/ambiguity tests |
| Large historical data safely | Target Architecture | D, E | #7, #8, #9 | UTC, bounded-memory, integrity/resume |
| Durable disconnection recovery | Target Architecture | C, F | #4, #6 | Migration/restart/outage tests |
| Secure controlled operations | Target Architecture | A, F, H | #10–#13, #15 | Security/redaction/rollback tests |

Implemented documentation must link an issue and test evidence when delivery
starts. Planned items remain explicitly non-implemented until their acceptance
criteria are met.
