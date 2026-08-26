---
title: Trust Center
description: Verify portable forecast evidence, back up or restore the allowlisted ledger, inspect local checkpoints, and read data-application receipts.
---

:::note[Availability]
Trust Center is verified on repository `main` after v0.18.0 and is not in the v0.18.0
installers. Read-only proof/archive preview and status checks work in source mode. Archive
restore and checkpoint creation require the private desktop launch token, so use a desktop
build from current source for those mutations. Open it from **Settings → Proofs, backups
& local integrity** or the footer. See [build the desktop app locally](/Golavo/installation/#build-the-desktop-app-locally).
:::

Trust Center groups four local integrity jobs without contacting a provider. They answer
different questions and deliberately do not collapse into one “verified” badge.

![Trust Center on source main with local proof verification, forecast-ledger backup and restore, ledger checkpoints, and data-application receipts](/Golavo/screenshots/trust-center-source-main.png)

*Source-main evidence after v0.18.0, captured with isolated local data; this screen is not
in the current installers.*

## Verify a forecast proof

Choose an exported `.proof.json`. The local engine verifies the bundle hash, each included
artifact, the connected lineage, source descriptors, and any embedded manifest hashes. It
does not persist the selected file.

The result separates embedded source manifests from descriptor-only sources. Verification
does **not** prove external source authenticity, ledger completeness, creation time, or
forecast accuracy; it proves only the bytes included in that proof.

## Forecast-ledger archive

**Download verified backup** writes a ZIP with fixed entry metadata and a checksummed
manifest that records the export time.
**Preview restore** validates its paths, sizes, hashes, contracts, SQLite follow database,
and named conflicts before any replacement can occur.

| Included | Excluded |
|---|---|
| Forecast artifacts | Team favorites in browser preferences |
| Picks and pick audit | Credentials and provider settings |
| Followed-match state | Licensed overlays and provider responses |
| | Weather and research captures |
| | Refresh generations, checkpoints, and derived caches |

Archives are bounded to 5,000 files and 64 MiB uncompressed. Unsafe, duplicate, symlink,
or out-of-allowlist paths fail closed. A conflicting restore stays disabled until you
confirm replacement of the exact listed files. The restore uses a durable recovery journal
and retains a pre-restore backup or quarantine copy so interruption does not silently leave
a half-applied ledger.

## Ledger checkpoints

A checkpoint hashes every verified `fa_*.json` artifact present at creation time and links
to the previous local checkpoint. Status walks the chain, detects cycles or changed bytes,
reports explicitly missing artifacts, and lists artifacts not yet in the current head.

The limit is important: this detects change relative to an earlier checkpoint on the same
installation. It does not prove external authenticity, prove that a forecast predates a
real-world event, prevent explicit deletion, or establish cross-version disaster recovery.
Migration drills, recovery proof, and optional external anchoring remain future gates.

## Data-application receipts

When an approved-source refresh generation activates or rolls back, Golavo attempts to
append a checksummed local receipt with the active generation, index hash, source summaries,
capability certificates, and a conservative stable-identity comparison. Unresolved rows
are counted separately and never guessed through an upstream rekey.

The active-pointer change and the secondary receipt append cannot be one filesystem
transaction. If Golavo stops between them, the persisted refresh job records the gap and
Trust Center shows it. A receipt is local application history, not an external tamper-proof
audit log.

See [The Prediction Ledger](/Golavo/prediction-ledger/),
[Updates & rollback](/Golavo/updates-rollback/), and
[Privacy & security](/Golavo/privacy-security/) for the surrounding boundaries.
