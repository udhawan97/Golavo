---
title: Installation
description: How to run Golavo — desktop installers with in-app updates, or source mode — with an honest note on the first-install OS warnings.
---

Choose the path that fits your machine on [Download & run](/Golavo/download/):

The current stable release is **[v0.11.1](https://github.com/udhawan97/Golavo/releases/tag/v0.11.1)**.
The website and the **latest release** link below always follow the newest stable build.

- **Browser UI** — source mode on macOS, Windows, or Linux.
- **macOS app** — Apple Silicon DMG, with no Python or terminal required.
- **Windows app** — x64 EXE or MSI, with no Python or terminal required.

The [website](/Golavo/#gv-install-title) includes platform-aware buttons that link
directly to the matching file in the newest stable GitHub release.

:::caution[Unsigned installers — first install only]
Desktop installers are **working but not OS-signed**: macOS Gatekeeper and
Windows SmartScreen warn on first install because there is no paid code-signing
certificate yet (see [Signing & notarization](#signing--notarization)).
**Updates are different**: they are cryptographically signed and verified
in-app, and don't re-trigger those warnings. Verify manual downloads against
`SHA256SUMS.txt` on the release.
:::

## Desktop app (recommended)

Use the direct buttons on the [Golavo website](/Golavo/#gv-install-title), or open the
[latest release](https://github.com/udhawan97/Golavo/releases/latest):

- **macOS (Apple Silicon)** — the `.dmg`. Open it and **drag Golavo into the
  Applications folder**, then launch it from Applications. This step matters:
  an app run straight from the disk image sits on a read-only volume and
  cannot update itself (the app will remind you if you forget).
- **Windows (x64)** — the `-setup.exe` (NSIS). The `.msi` also works; both
  update in-app afterwards.

On first launch the OS will warn (unsigned build):

- **macOS** — "Golavo can't be opened because Apple cannot check it for
  malicious software." Right-click the app → **Open** → **Open**, or clear the
  quarantine flag: `xattr -dr com.apple.quarantine /Applications/Golavo.app`.
- **Windows** — SmartScreen shows "Windows protected your PC." Click **More
  info** → **Run anyway**.

### Optional: add local AI with Ollama

Golavo's deterministic match analysis works without AI. If you want the optional
Fast or Deep narrative, open **Settings → Local intelligence** after installation:

1. Use Golavo's link to install [Ollama for macOS](https://ollama.com/download/mac),
   then keep Ollama open.
2. Choose **Check again** so Golavo can confirm the loopback service is ready.
3. Download the recommended Fast or Deep model inside Golavo. The app shows progress,
   transferred size, and a cancel action, then assigns the model automatically.

The same guide appears beside the AI analysis controls. Model installation is explicit,
stores the model locally through Ollama, and never uploads match data. Full details:
[AI providers & local models](/Golavo/ai/providers/#set-up-ollama-inside-golavo).

### Staying up to date

From v0.2.1 on, Golavo updates **in-app**: a one-time card asks whether to
check for updates automatically (your choice; a manual **Check now** always
lives in **Settings → Updates**), and installs happen only when you click.
Every update is signature-verified before install and your ledger is backed up
first — see [Updates & rollback](/Golavo/updates-rollback/).

When an automatic or manual check finds a newer stable GitHub release, Golavo shows
a visible in-app notification and keeps an **Update available** button in the header
until you review, install, or skip that version. The macOS and Windows installers linked
from the website are release builds with this updater compiled in; the stable release
workflow refuses to publish them if updater signing is unavailable.

**Coming from v0.1.0 or v0.2.0?** Those builds predate the updater — download and install
the current version manually once; it's in-app from then on.

:::caution[Uninstalling on Windows]
The uninstaller offers to *delete application data*. **Leave that unchecked**
if you want to keep your prediction ledger — it lives in that data folder.
:::

## Browser UI from source

This is a local web app: the API listens only on `127.0.0.1`, the UI opens at
`http://127.0.0.1:5173`, and nothing is hosted by Golavo.

```bash
git clone https://github.com/udhawan97/Golavo.git
cd Golavo
cp .env.example .env     # optional; Golavo runs local with no keys
make setup               # install core + server + ui dev deps
make dev                 # start both services and open the browser UI
```

Press `Ctrl+C` in that terminal to stop both local services. To start without
opening a new browser tab, use `python scripts/dev.py --no-open`.

Source checkouts update with `git pull`; the in-app updater stays out of the
way (Settings says so instead of showing dead controls). See
[Build from source](/Golavo/build-from-source/) for prerequisites.

## Build the desktop app locally

Prerequisites: Rust (stable), Node 22+, Python 3.12+, and the Tauri system
dependencies for your OS. Then:

```bash
# from the repo root
packaging/build.sh aarch64-apple-darwin      # or x86_64-pc-windows-msvc, etc.
```

The bundle and a per-target `SHA256SUMS-<target>` land in `packaging/out/`:

- **macOS** — a `.dmg` (and `.app`; plus the `.app.tar.gz` updater artifact
  when the signing key is present).
- **Windows** — an `.msi` (WiX) and an `-setup.exe` (NSIS) installer.

CI (`.github/workflows/release.yml`) builds these on native macOS and Windows
runners for every `v*` tag, assembles the update manifest, and publishes the
release atomically (draft until every asset is uploaded).

## Signing & notarization

- **macOS** notarization requires the **Apple Developer Program** ($99/yr) for a
  Developer ID certificate. Without it, no notarized release is possible.
- **Windows** signing uses SignPath Foundation (free for OSS) or Azure Trusted
  Signing.
- **Signed auto-update** is **active**: updates are signed with the Tauri
  updater key in CI and verified in-app before installing. This is independent
  of (and unaffected by) the OS-level signing above.

The first two are still gated on secrets the project does not hold; the
pipeline skips those steps honestly rather than faking them. See
[Updates & rollback](/Golavo/updates-rollback/).
