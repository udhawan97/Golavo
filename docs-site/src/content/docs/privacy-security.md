---
title: Privacy & security
description: What Golavo stores locally, which optional actions use the network, and how trust boundaries fail closed.
---

Golavo runs from local files and has no accounts, telemetry, ads, crash reporter, or
hosted forecasting backend. Core match exploration and deterministic analysis work offline.

## Privacy

- **No account or telemetry.** No sign-up, cloud profile, analytics, advertising ID, or
  usage upload exists.
- **Network use is feature-specific and consent-gated.** Approved-source refresh,
  OpenLigaDB, match research, cloud AI and update checks are separate choices. Enabling one
  does not enable the others.
- **Following stays local.** Follow state and event history live in Application Support.
  Checks run on launch and periodically only while Golavo is open. No daemon, Login Item,
  LaunchAgent, cloud push, or closed-app monitoring is installed.
- **Research captures only selected sources.** Wikimedia discovery can suggest a page or
  entity. A fetch starts only after explicit selection and retains source text, URL,
  retrieval time and hash for local review. `GOLAVO_NO_RESEARCH=1` disables the lane.
- **BYOK keys stay yours.** Cloud-provider keys are read from the OS keychain or an
  environment variable, sent only in the selected provider request header, and excluded
  from artifacts, logs, caches and exports. Local models stay on loopback.
- **Update checks are separate.** Until you answer the one-time consent card, no update
  check occurs. Enabled checks ask GitHub for release metadata at most once a day; an
  installer downloads only after you click.

## Security model

| Surface | Protection |
|---|---|
| Desktop API | Private `127.0.0.1` port, random per-launch token, narrow CORS policy, request-size limits, and token-gated mutation/research routes. Source/browser mode disables desktop-only writes. |
| Core refresh | Fixed source and path allowlists, bounded downloads, immutable raw receipts and hashes, parser/schema checks, atomic activation, previous-generation rollback, and last-known-good operation on failure. |
| OpenLigaDB | Separate Application Support root and SQLite schema, ODbL-only source IDs, no bundled response bytes, display-only read model, explicit attribution, and deletion independent of core data. |
| Research fetch | HTTPS host/path/method allowlists, DNS/IP checks, pinned connection target, redirect validation, response/time limits, hostile-markup sanitization, prompt fencing, exact quote matching, cancellation and a global kill switch. |
| Corrections | User input begins untrusted; source URL and captured evidence are required before validation. Text is sanitized, history is append-only, conflicts fail closed, and external export requires a separate explicit action. |
| Source packs | Upstream revisions and every vendored byte are SHA-256 checked against manifests. Minisign authenticity verification remains planned under ADR-0001 and must not be implied today. |
| Forecast artifacts | Canonical payload hash and source/build identity; scoring appends a successor rather than mutating a sealed forecast. Research, follows, overlays and corrections have no probability write path. |
| Optional AI | Numeric whitelist, schema/citation/quote guards, betting-language filter, loopback-only local endpoints, fixed cloud providers, no chain-of-thought exposure, and deterministic-only fallback. |
| Signed auto-update | Update payloads are verified against the public key embedded in the app before install. Installers themselves are not yet OS code-signed/notarized. |

## Update and data recovery

Before an in-app update, Golavo backs up the local ledger. The first launch of the new
build health-checks the sidecar. If it is unhealthy, the ledger restore is staged and the
app links to the previous release; reverting the **binary** is manual. Golavo keeps only
the latest retired live-ledger generation so recovery does not grow without bound. See
[Updates & rollback](/Golavo/updates-rollback/).

To report a vulnerability, follow `SECURITY.md`; do not open a public issue.
