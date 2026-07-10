---
title: Updates & rollback
description: How Golavo updates itself safely — signed artifacts, a backup before every update, a health check after, and one-click rollback.
---

Golavo's desktop updates are designed to be safe by default. (This lands in Phase 4; documented here so the contract is clear.)

## The update path

1. **Check** — the app checks for updates (you can disable this). It is the only default network call.
2. **Verify** — the downloaded artifact's signature and SHA-256 checksum are verified before anything is applied.
3. **Back up** — a pre-update snapshot of your database and settings is created and verified. If the backup can't be verified, the update aborts.
4. **Install** — the signed installer applies the update. On Windows the app is force-exited by the installer, so the sidecar is shut down first.
5. **Health check** — on relaunch, the app records launch health. Repeated failed launches trigger a **rollback offer**.

## Rollback

Rollback restores the pre-update database and settings backup. Your settings and forecast ledger live separately from the app binary, so they survive updates and restores.

## Channels

Two channels share one pipeline: **stable** (from a `v*` tag) and **beta** (an opt-in prerelease). You choose your channel in settings.

## Signing

macOS builds are signed with a Developer ID and notarized. Windows builds are code-signed. Update artifacts additionally carry an updater signature, verified against a key pinned in the app. A lost signing key would permanently strand installed users, so keys are escrowed offline before any public release.
