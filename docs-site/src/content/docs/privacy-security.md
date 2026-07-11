---
title: Privacy & security
description: What Golavo does and does not do with your data, and how the local app is secured.
---

Golavo runs from local files and has no accounts, telemetry, or ads. The one optional network path — the AI Deep Read layer — is **off by default**.

## Privacy

- **No account.** No sign-up, no cloud profile.
- **No telemetry, no ads.** Nothing about your usage is collected or sold.
- **No runtime network call unless you opt in.** Rebuilding the pinned sourcepack is an explicit network action. The AI layer is off by default; enabling it contacts either a local model (Ollama / llama.cpp) or a BYOK cloud provider you choose. Update checks (desktop app) follow the same rule: off until you answer the one-time consent card, and even then only a once-a-day "is there a newer version?" request to GitHub — downloads start only when you click.
- **BYOK keys stay yours.** A cloud provider key is read from your environment or the OS keychain, sent only in the request header, and never logged or written into an artifact. Golavo ships with the AI layer disabled.
- **Crash reports are local.** You choose whether to attach one to a GitHub issue.

## Security model

| Surface | Protection |
|---|---|
| Source API | Read-only routes; CORS allows only the local dev origins and the Tauri webview; source mode is unauthenticated, the desktop sidecar adds an `x-golavo-token` gate on `/api/*`. |
| Source pack | Upstream commit pinned; every vendored byte is SHA-256 checked against its manifest. |
| Forecast artifacts | Canonical payload hash; scoring creates a new artifact rather than mutating a seal. |
| Desktop sidecar | Binds a private `127.0.0.1` port with a per-launch token; the AI gateway strips chain-of-thought, rejects unsupported numbers, and never logs keys. |
| Signed auto-update | **Active** (desktop, v0.2.0+): consent-first checks; every update is signature-verified against the public key compiled into the app before install, with a ledger backup + health-checked first boot (see [Updates & rollback](/Golavo/updates-rollback/)). |
| Signed packs, DB migrations | Wired but **gated on secrets** (ADR-0001); disabled by default. |

To report a vulnerability, see the repository's `SECURITY.md`. Please do not open a public issue for security problems.
