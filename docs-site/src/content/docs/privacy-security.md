---
title: Privacy & security
description: What Golavo does and does not do with your data, and how the local app is secured.
---

Golavo runs from local files and has no accounts, telemetry, or ads. The one optional network path — the AI Deep Read layer — is **off by default**.

## Privacy

- **No account.** No sign-up, no cloud profile.
- **No telemetry, no ads.** Nothing about your usage is collected or sold.
- **No runtime network call unless you opt in.** Rebuilding the pinned sourcepack is an explicit network action. The AI layer is off by default; enabling it contacts either a local model (Ollama / llama.cpp) or a BYOK cloud provider you choose. **AI web research** is a further, separate opt-in: when on, a read fetches a few pages from a fixed allowlist (`en.wikipedia.org` and DuckDuckGo's keyless HTML search) over https with a proper User-Agent, and never posts your data anywhere; it is disabled entirely by `GOLAVO_NO_RESEARCH=1`. Update checks (desktop app) follow the same rule: off until you answer the one-time consent card, and even then only a once-a-day "is there a newer version?" request to GitHub — downloads start only when you click.
- **BYOK keys stay yours.** A cloud provider key is read from your environment or the OS keychain, sent only in the request header, and never logged or written into an artifact. Golavo ships with the AI layer disabled.
- **No crash reporting.** No crash reporter exists — nothing about your usage, forecasts, or keys is collected or sent anywhere.

## Security model

| Surface | Protection |
|---|---|
| Source API | Read-only routes; CORS allows only the local dev origins and the Tauri webview; source mode is unauthenticated, the desktop sidecar adds an `x-golavo-token` gate on `/api/*`. |
| Source pack | Upstream commit pinned; every vendored byte is **SHA-256 checked** against its manifest, so today's check catches corruption. Minisign **signature** verification against a pinned public key (authenticity, plus an unsigned-pack override) is **planned (ADR-0001), not yet implemented**. |
| Forecast artifacts | Canonical payload hash; scoring creates a new artifact rather than mutating a seal. |
| Desktop sidecar | Binds a private `127.0.0.1` port with a per-launch token; the AI gateway strips chain-of-thought, rejects unsupported numbers, and never logs keys. |
| Signed auto-update | **Active** (desktop, v0.2.1+): consent-first checks; every update is signature-verified against the public key compiled into the app before install, with a ledger backup + health-checked first boot (see [Updates & rollback](/Golavo/updates-rollback/)). The installers themselves are **not yet OS code-signed/notarized**. |
| Update safety | On update the ledger is backed up and the new build is health-checked; a build that fails to launch is rolled back to the previous version. There is **no database or migration layer** today. |

To report a vulnerability, see the repository's `SECURITY.md`. Please do not open a public issue for security problems.
