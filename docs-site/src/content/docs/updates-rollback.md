---
title: Updates & rollback
description: How Golavo updates itself — consent-first checks, signed downloads, a ledger backup before every install, a health check after, and honest recovery when something goes wrong.
---

Golavo updates **from inside the app** — no git, no terminal. The updater is
consent-first, every download is cryptographically verified before it installs,
and your ledger is backed up before anything is touched.

:::note[Which builds update in-app]
Release builds from the [releases page](https://github.com/udhawan97/Golavo/releases)
(v0.2.0 and later). Source checkouts update with `git pull`; development builds
without the signing key say so honestly in **Settings → Updates** instead of
showing dead buttons. **v0.1.0 installs predate the updater** — update from
them with one manual download; it's in-app from then on.
:::

## Consent first

Golavo promises *no runtime network call unless you opt in*. The updater keeps
that promise: on first launch a one-time card asks **"Keep Golavo up to
date?"**. Until you answer, nothing is checked. Enabled, Golavo asks GitHub
once a day (and shortly after launch) whether a newer version exists — nothing
else leaves your machine, and downloads only start when you click. The toggle
lives in **Settings → Updates**, next to a manual **Check now** that always
works regardless of the toggle.

## The update path

1. **Check** — the app reads a static `latest.json` from the latest GitHub
   release (natively, via `tauri-plugin-updater`; the webview never talks to
   GitHub).
2. **Offer** — a passive "Update available" pill appears in the header. The
   Software Update sheet shows the version, release notes, and three honest
   choices: **Update now**, **Skip this version** (silences reminders for that
   version only — a manual check still tells you it exists), or **Later**.
3. **Download & verify** — streamed with a progress bar and a working Cancel.
   The artifact's signature is verified against the public key compiled into
   the app *before* anything installs; a tampered or wrongly-signed download
   is rejected outright.
4. **Back up** — your ledger is snapshotted to
   `…/com.golavo.app/backups/pre-update/` immediately before install.
5. **Install & restart** — on your explicit click. macOS swaps the app bundle
   in place and restarts ("Restart Golavo"); Windows quits into the installer,
   which updates and reopens Golavo itself ("Quit & install"). The shell stops
   the sidecar first in both cases.
6. **Health check** — the first launch of the new version runs the normal
   `/health` gate:
   - **healthy** → the backup is retired and a one-time toast confirms
     "Updated to Golavo X — your ledger was backed up before installing";
   - **unhealthy** → your ledger is **restored from the backup** and a native
     dialog explains what happened, with a link to download the previous
     version. No silent failures, no invisible crashes.

## Rollback — what is and isn't automatic

The pre-update backup is **armed only between install and the first healthy
launch** of the new version. A restore can never fire twice, and an unrelated
sidecar hiccup months later can never overwrite newer ledger data with an old
snapshot. Restores are staged (copy, move the live ledger aside, rename into
place) — the previous live state is kept on disk, never deleted.

Reverting the **binary** to a previous version remains a manual download from
the releases page — the failure dialog links straight to it. The updater
protects your data; it does not (yet) roll back the executable.

## Trust model

| Layer | Status |
|---|---|
| Update authenticity | **Active** — every update is signed in CI and verified in-app against the embedded public key before install |
| Download integrity | **Active** — `SHA256SUMS.txt` published with every release for manual verification |
| macOS Developer ID + notarization | Not configured (Apple Developer Program) — Gatekeeper warns on **first install only**; in-app updates don't re-trigger it |
| Windows code signing | Not configured (SignPath / Azure Trusted Signing) — SmartScreen warns on **first install only** |

The updater signing key is **fatal if lost** — installed apps could never
accept another update — so it is escrowed offline and in the repository's CI
secrets (`TAURI_SIGNING_PRIVATE_KEY`). The release workflow refuses to cut a
stable release without it, and refuses a tag whose version doesn't match the
committed one (`scripts/bump_version.py --check`).

## For maintainers

Releasing:

```bash
make release-bump VERSION=0.2.0   # sync all version spots
git commit -am "release: v0.2.0" && git tag v0.2.0 && git push --tags
```

CI builds both platforms, assembles and validates `latest.json`
(`scripts/make_update_manifest.py`), publishes everything as a **draft**, and
only then flips it live — the update endpoint never sees a half-uploaded
release. Stable tags publish as real (non-pre-) releases; `workflow_dispatch`
beta builds never publish at all.

Exercise the full flow locally before a release with
`scripts/test-updater-local.sh` (builds the current + a bumped version, serves
them over loopback, and walks you through the checklist, including the
tampered-signature rejection test).
