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
| **Local sidecar** | Binds loopback (`127.0.0.1`) on an ephemeral port — a non-loopback bind is refused outright. Every `/api` request requires a per-launch token, handed to the sidecar through its **environment** (not a command-line argument), so it is not exposed in the process list. CORS is limited to the local dev and Tauri webview origins; the CSP restricts connections to self and loopback. |
| **Provider keys** | Read from an environment variable, or on macOS the login keychain (`security`); sent only in a request header, and **never** written to artifacts, caches, logs, or responses (the AI gateway logs no request bodies or headers). There is no Windows/Linux credential store yet — those platforms use the environment variable. |
| **Prompt injection** | Fetched text is sanitized and delimited as untrusted; the model has no shell/file tools; a CI red-team suite must fail closed on any attempt to change a probability or exfiltrate a key. |
| **Data / model packs** | **Hash-verified before load:** each pack carries a per-file SHA-256 manifest, and every retained snapshot's manifest hash is pinned in `packs/snapshots.json`; the app re-hashes every declared file. Minisign **signature** verification against a pinned public key (authenticity, plus an unsigned-pack override) is **planned (ADR-0001), not yet implemented** — because the manifest lives inside the pack, today's check catches corruption, not a forged pack. |
| **Updates** | In-app updates are **cryptographically signed in CI and verified against a pinned public key** before install (v0.2.1+); every release asset also carries a SHA-256 checksum. The installers themselves are **not yet OS code-signed/notarized**, so a first manual install warns on macOS Gatekeeper / Windows SmartScreen. The signing key lives in offline escrow plus a CI secret. |
| **Update safety** | On update the ledger is backed up and the new build is health-checked; a build that fails to launch is rolled back to the previous version. There is no database or migration layer today. |
| **Telemetry** | None. No crash reporting exists — nothing about your usage, forecasts, or keys is collected or sent anywhere. |

## Out of scope

Vulnerabilities requiring a compromised local OS account, physical access, or
malicious third-party API keys the user themselves supplied.
