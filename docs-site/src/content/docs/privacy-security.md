---
title: Privacy & security
description: What Golavo does and does not do with your data, and how the local app is secured.
---

Phase 0 runs from local files. It has no accounts, telemetry, AI, provider keys, desktop sidecar, or updater.

## Privacy

- **No account.** No sign-up, no cloud profile.
- **No telemetry, no ads.** Nothing about your usage is collected or sold.
- **No default runtime network call.** Rebuilding the pinned sourcepack is an explicit network action.
- **No BYOK adapters in Phase 0.** Local key handling is planned (ADR-0001).
- **Crash reports are local.** You choose whether to attach one to a GitHub issue.

## Security model

| Surface | Protection |
|---|---|
| Source API | Read-only routes; CORS allows only `127.0.0.1:5173` and `localhost:5173`; no source-mode auth. |
| Source pack | Upstream commit pinned; every vendored byte is SHA-256 checked against its manifest. |
| Forecast artifacts | Canonical payload hash; scoring creates a new artifact rather than mutating a seal. |
| Sidecar, provider keys, prompt injection, signed packs/updates, migrations | Planned (ADR-0001); not Phase 0 capabilities. |

To report a vulnerability, see the repository's `SECURITY.md`. Please do not open a public issue for security problems.
