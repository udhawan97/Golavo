---
title: Installation
description: How to run Golavo — source mode today, plus unsigned desktop builds (Phase 4) with an honest note on the OS warnings they trigger.
---

:::caution[Unsigned desktop builds]
Phase 4 produces **working but unsigned** desktop bundles. They launch and run
the full local app, but macOS Gatekeeper and Windows SmartScreen will warn that
the developer is unidentified — because there is no paid code-signing certificate
yet (see [Signing & notarization](#signing--notarization)). Signed, notarized,
auto-updating releases activate only once the signing secrets are configured.
:::

## Source mode (developers, researchers)

```bash
git clone https://github.com/udhawan97/Golavo.git
cd Golavo
cp .env.example .env     # optional; Golavo runs local with no keys
make setup               # install core + server + ui dev deps
make dev                 # run the FastAPI core + Vite UI on 127.0.0.1
```

See [Build from source](/Golavo/build-from-source/) for prerequisites.

## Desktop app (Phase 4)

Golavo packages as a [Tauri 2](https://tauri.app) desktop shell that launches a
bundled Python **sidecar** (the FastAPI core, frozen with PyInstaller) on a
private loopback port, waits for its health check, then shows the workbench. On
quit, the shell kills the sidecar.

### Build it locally

Prerequisites: Rust (stable), Node 20+, Python 3.12, and the Tauri system
dependencies for your OS. Then:

```bash
# from the repo root
packaging/build.sh aarch64-apple-darwin      # or x86_64-pc-windows-msvc, etc.
```

The bundle and a `SHA256SUMS` land in `packaging/out/`:

- **macOS** — a `.dmg` (and `.app`).
- **Windows** — an `.msi` (WiX) and an `.exe` (NSIS) installer.

CI (`.github/workflows/release.yml`) builds these same **unsigned** artifacts on
native macOS and Windows runners for every `v*` tag.

### Running an unsigned build

Because the build is unsigned, the OS will warn on first launch:

- **macOS** — "Golavo can't be opened because Apple cannot check it for
  malicious software." Right-click the app → **Open** → **Open**, or clear the
  quarantine flag: `xattr -dr com.apple.quarantine /Applications/Golavo.app`.
- **Windows** — SmartScreen shows "Windows protected your PC." Click **More
  info** → **Run anyway**.

These warnings are expected for unsigned software and disappear once signing and
notarization are in place.

## Signing & notarization

- **macOS** notarization requires the **Apple Developer Program** ($99/yr) for a
  Developer ID certificate. Without it, no notarized release is possible.
- **Windows** signing uses SignPath Foundation (free for OSS) or Azure Trusted
  Signing.
- **Signed auto-update** requires the Tauri updater key pair; the update flow is
  wired but stays inert until that key is configured.

All three are **gated on secrets** the project does not yet hold. The build
pipeline is complete and will emit signed, notarized, auto-updating releases the
moment those secrets are set — nothing here is faked in the meantime. See
[Updates & rollback](/Golavo/updates-rollback/).
