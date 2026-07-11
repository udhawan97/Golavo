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
| **Data / model packs** | **Hash-verified before load:** each pack carries a per-file SHA-256 manifest, and every retained snapshot's manifest hash is pinned in `packs/snapshots.json`; the app re-hashes every declared file. Minisign **signature** verification against a pinned public key (authenticity, plus an unsigned-pack override) is **planned (ADR-0001), not yet implemented** — because the manifest lives inside the pack, today's check catches corruption, not a forged pack. |
| **Updates** | A Tauri auto-updater has landed but is **gated on signing secrets that are not configured**, so released desktop builds are **unsigned pre-releases** carrying SHA-256 checksums only. The signed updater, signed artifacts, and offline signing-key escrow remain **planned (ADR-0001)** before any stable, signed release. |
| **Migrations** | Backup-before-migrate, row-count verification, and a rollback offer on repeated failed launches. |
| **Telemetry** | None. Crash reports are written locally; the user chooses whether to attach them to an issue. |

## Out of scope

Vulnerabilities requiring a compromised local OS account, physical access, or
malicious third-party API keys the user themselves supplied.
