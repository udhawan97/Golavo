---
title: Privacy & security
description: What Golavo does and does not do with your data, and how the local app is secured.
---

Golavo is local-first. Your data and keys stay on your machine.

## Privacy

- **No account.** No sign-up, no cloud profile.
- **No telemetry, no ads.** Nothing about your usage is collected or sold.
- **One default network call:** the update check — and you can disable it.
- **BYOK data stays local.** Data fetched with your provider key is rendered in your private session, never exported by default, and purged when you remove the key.
- **Crash reports are local.** You choose whether to attach one to a GitHub issue.

## Security model

| Surface | Protection |
|---|---|
| Local sidecar | Bound to `127.0.0.1` on an ephemeral port; every request needs a per-launch token. Strict CORS/CSP. |
| Provider keys | OS keychain only — never in the database, logs, or exports. Redaction filter on all logging. |
| Prompt injection | Fetched text sanitized and delimited as untrusted; the model has no shell/file tools; CI red-team suite fails closed. |
| Data/model packs | Signature-verified against a pinned key and hash-checked before load. |
| Updates | Signed updater artifacts + SHA-256 checksums; signing keys escrowed offline. |
| Migrations | Backup-before-migrate, verify, and rollback offer on repeated failed launches. |

To report a vulnerability, see the repository's `SECURITY.md`. Please do not open a public issue for security problems.
