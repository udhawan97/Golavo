# Security Policy

## Reporting a vulnerability

**Do not open a public issue for security reports.**

Use GitHub's [private vulnerability reporting](https://github.com/udhawan97/Golavo/security/advisories/new)
or email **umangdhawan97@gmail.com** with subject `GOLAVO SECURITY`. Please include
reproduction steps and affected version/commit. We aim to acknowledge within 5 days
and to disclose responsibly after a fix ships.

## Supported versions

Pre-1.0: only the latest `main` and the most recent release receive fixes.

## Scope & design commitments

Golavo is local-first; the biggest surfaces are the local sidecar, user-supplied
keys, optional AI, and the update path.

| Area | Commitment |
|---|---|
| **Local sidecar** | Binds `127.0.0.1` on an ephemeral port; every request requires a per-launch token. Strict CORS/CSP locked to the app origin. |
| **Provider keys** | Stored in the OS keychain only — never in SQLite, logs, exports, or crash reports. A redaction filter runs on all logging. |
| **Prompt injection** | Fetched text is sanitized and delimited as untrusted; the model has no shell/file tools; a CI red-team suite must fail closed on any attempt to change a probability or exfiltrate a key. |
| **Data / model packs** | Signature-verified (minisign) against a pinned public key and hash-checked before load. Unsigned packs require explicit user override. |
| **Updates (planned, ADR-0001)** | Phase 0 has no updater. A future desktop release requires signed artifacts, SHA-256 checksums, and offline signing-key escrow before public release. |
| **Migrations** | Backup-before-migrate, row-count verification, and a rollback offer on repeated failed launches. |
| **Telemetry** | None. Crash reports are written locally; the user chooses whether to attach them to an issue. |

## Out of scope

Vulnerabilities requiring a compromised local OS account, physical access, or
malicious third-party API keys the user themselves supplied.
