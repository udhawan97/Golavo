---
title: Installation
description: The run modes Golavo will support — source-mode today (as it's built), desktop installers later.
---

:::caution[Pre-alpha]
There is no installable build yet. Golavo is in Phase 0. This page describes the planned install modes; follow the [Roadmap](/Golavo/roadmap/) for progress.
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

## Desktop (everyone) — Phase 4

Signed installers will be published on GitHub Releases:

- **macOS** — a notarized `.dmg` (Apple Silicon).
- **Windows** — a signed `.exe` installer (per-user, no admin required).

Desktop builds include in-app signed updates with pre-update backup and one-click rollback. Until code signing is in place for a given platform, beta builds may show an OS "unidentified developer"/SmartScreen warning; that is expected and documented per release.
