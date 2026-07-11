# desktop

The Golavo desktop shell (**Tauri 2**). **Apache-2.0.** Landed in **Phase 4** —
see [ADR-0001](../docs/adr/0001-architecture.md).

The shell is a thin Rust supervisor; all forecasting stays in the Python sidecar.

## What it does

- Picks a free `127.0.0.1` port and mints a per-launch 256-bit token.
- Spawns the PyInstaller sidecar (`golavo-sidecar-<target-triple>`, a Tauri
  `externalBin`) with that port + token and a per-user ledger directory.
- Waits for the sidecar's `/health` (bounded 90s) before showing the window.
- Injects `window.__GOLAVO_RUNTIME__ = { apiBase, token }` so the bundled UI
  talks to the ephemeral port — nothing is hardcoded.
- Kills the sidecar on every exit path (`RunEvent::ExitRequested`/`Exit`). As a
  safety net the sidecar also watches the shell pid (`--parent-pid`) and
  self-exits if it is orphaned — the PyInstaller onefile bootloader forks a
  Python child the shell's kill can't reach directly.
- Signed auto-updates with pre-update backup + rollback are **wired but gated**
  behind the `updater` Cargo feature and the signing secrets (see
  [updates-rollback](../docs-site/src/content/docs/updates-rollback.md)).

## Layout

```
desktop/
  package.json            @tauri-apps/cli (prebuilt) + scripts
  src-tauri/
    Cargo.toml            crate + gated `updater` feature
    tauri.conf.json       base config (unsigned; strict CSP; externalBin)
    tauri.updater.conf.json  GATED overlay for signed maintainer builds
    capabilities/         window/dialog/shell permissions
    icons/                generated from the brand mark
    binaries/             the frozen sidecar is copied here at build time (gitignored)
    src/
      main.rs             entry
      lib.rs              lifecycle: port/token -> spawn -> health gate -> window -> kill
      health.rs           free port, token, /health probe
      updater.rs          gated updater: backup / check / install / rollback
```

## Build / run

```bash
# from the repo root — freezes the sidecar, builds the UI, then the bundle:
packaging/build.sh aarch64-apple-darwin

# or, iterating on the shell against a source-mode UI:
cd desktop && npm ci && npm run dev
```

Sidecar binaries must be named `golavo-sidecar-<target-triple>` per platform; the
updater signing key is fatal-if-lost and is escrowed offline before any public
release.
