---
title: Privacy & security
description: What Golavo stores locally, which optional actions use the network, and how trust boundaries fail closed.
---

Golavo runs from local files and has no accounts, telemetry, ads, crash reporter, or
hosted forecasting backend. Core match exploration and deterministic analysis work offline.

:::note[Source boundary]
The Trust Center archive, checkpoint, proof-inspection, and application-receipt surfaces
described below are on repository `main` after v0.18.0. Archive restore and checkpoint
creation require the private desktop launch token; they are not open source-mode mutations.
:::

## Privacy

- **No account or telemetry.** No sign-up, cloud profile, analytics, advertising ID, or
  usage upload exists.
- **Network use is feature-specific and consent-gated.** Approved-source refresh,
  OpenLigaDB, match research, cloud AI and update checks are separate choices. Enabling one
  does not enable the others.
- **Following stays local.** Follow state and event history live in Application Support.
  Checks run on launch and periodically only while Golavo is open. No daemon, Login Item,
  LaunchAgent, cloud push, or closed-app monitoring is installed. Calendar export is a
  static file containing only exact-time followed fixtures, not a subscription.
- **Team favorites stay local.** My Teams uses a browser preference keyed by exact
  competition/team identity. It creates no profile, enables no provider, and is excluded
  from the forecast-ledger archive.
- **Local removal stays explicit.** Follow history, all correction proposals, and individual
  evidence captures each open a separate Cancel/Remove choice. Cancel or Escape disarms the
  choice and restores focus; no removal occurs until the separately named destructive action.
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
| Local deletion | Follow history, all-proposal removal, and individual-evidence removal disclose their exact scope, keep Cancel visible, support Escape, and do not mutate data until the separately named destructive action. |
| Source packs | Upstream revisions and every vendored byte are SHA-256 checked against manifests. Official frozen bundles also require a detached Minisign signature over every active pack manifest; a missing or altered signature fails before pack data is read. Locally generated refresh generations use immutable receipts, verified manifests, and atomic activation instead. |
| Forecast artifacts | Canonical payload hash and source/build identity; scoring appends a successor rather than mutating a sealed forecast. A portable proof download carries the connected lineage and any matching source manifests for offline verification. Research, follows, overlays and corrections have no probability write path. |
| Trust Center | Uploaded proofs and archives are checked locally. Archive paths, counts, sizes, hashes, contracts, SQLite content, and conflicts are validated before restore; restore/checkpoint mutations require the private desktop launch token. Local checkpoints detect changed forecast bytes but do not prove external authenticity or timing. |
| Optional AI | Numeric whitelist, schema/citation/quote guards, betting-language filter, loopback-only local endpoints, fixed cloud providers, no chain-of-thought exposure, and deterministic-only fallback. |
| Signed auto-update | Update payloads, official pack manifests, and the aggregate release checksum ledger are verified against Golavo's pinned release identity. Installers themselves are not yet OS code-signed/notarized. |

## Update and data recovery

Before an in-app update, Golavo backs up the local ledger. The first launch of the new
build health-checks the sidecar. If it is unhealthy, the ledger restore is staged and the
app links to the previous release; reverting the **binary** is manual. Golavo keeps only
the latest retired live-ledger generation so recovery does not grow without bound. See
[Updates & rollback](/Golavo/updates-rollback/).

Trust Center's user-requested archive is separate from that automatic pre-update backup.
It includes only forecast artifacts, picks, and followed-match state; excludes preferences,
credentials, providers, overlays, weather, research, refresh generations, checkpoints, and
caches; previews exact conflicts before replacement; and retains a verified pre-restore
backup or quarantine copy. See [Trust Center](/Golavo/trust-center/).

To report a vulnerability, follow `SECURITY.md`; do not open a public issue.
