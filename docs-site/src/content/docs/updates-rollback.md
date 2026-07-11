---
title: Updates & rollback
description: How Golavo updates itself safely — signed artifacts, a backup before every update, a health check after, and rollback — and exactly what is gated until signing keys exist.
---

Golavo's desktop updater is **fully wired but gated**: the code path exists and
compiles, but a default build ships with it **inert** because no signing key
exists yet. This page describes the contract and states plainly what is active
today versus what needs secrets.

:::note[What's active today]
Nothing auto-updates in an unsigned build. `check_for_update` returns
`disabled`. Signed auto-update turns on only when the updater key pair is
configured and the app is built with `--features updater`.
:::

## The update path (when enabled)

1. **Check** — the app queries a static `latest.json` on GitHub Releases via
   `tauri-plugin-updater`.
2. **Verify** — the downloaded artifact's updater signature is verified against
   the public key embedded in the app before anything is applied.
3. **Back up** — a pre-update snapshot of your ledger (and, in future, settings)
   is copied to `…/com.golavo.app/backups/pre-update/`.
4. **Install** — the signed installer applies the update. On Windows the
   installer force-exits the app, so the shell kills the sidecar first.
5. **Health check** — on relaunch the shell runs its normal `/health` gate. If
   the freshly updated sidecar fails to come up, the shell **restores the
   pre-update backup** of your data so a bad update cannot strand it.

## Rollback

Rollback restores the pre-update **data** backup (your ledger). Your data lives
in the per-user app-data directory, separate from the app binary, so it survives
updates and restores.

Reverting the **binary** itself to a previous version still requires reinstalling
the prior release — the updater protects your data, not the executable. This is a
known limitation, tracked for a future release.

## Channels

Two channels share one pipeline: **stable** (from a `v*` tag) and **beta** (an
opt-in prerelease).

## Signing (what's gated, and on which secrets)

| Capability | Gated on | Status |
|---|---|---|
| macOS Developer ID signing + notarization | Apple Developer Program ($99/yr): `APPLE_CERTIFICATE`, `APPLE_SIGNING_IDENTITY`, `APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID` | not configured |
| Windows code signing | SignPath Foundation / Azure Trusted Signing | not configured |
| Signed auto-update | Tauri updater key pair: `TAURI_SIGNING_PRIVATE_KEY` (+ password) and the paired public key in `tauri.updater.conf.json` | not configured |

The updater signing key is **fatal if lost** — installed users would be stranded
— so it is escrowed offline before any public release. None of these keys are
fabricated; the pipeline simply skips the corresponding step when its secret is
absent, producing an honest unsigned build.

### Enabling signed updates (for maintainers)

```bash
# with the updater key pair in your environment and the real public key
# substituted into src-tauri/tauri.updater.conf.json:
TAURI_SIGNING_PRIVATE_KEY=… TAURI_SIGNING_PRIVATE_KEY_PASSWORD=… \
  packaging/build.sh aarch64-apple-darwin
```

`build.sh` detects `TAURI_SIGNING_PRIVATE_KEY` and adds
`--features updater --config src-tauri/tauri.updater.conf.json`, producing signed
bundles plus the updater artifacts and `latest.json` inputs.
