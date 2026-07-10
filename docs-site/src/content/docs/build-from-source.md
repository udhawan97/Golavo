---
title: Build from source
description: Prerequisites and commands to run Golavo locally as it's being built.
---

## Prerequisites

- **Python** 3.11+
- **Node** 20+
- (Phase 4 only) **Rust** stable + the Tauri prerequisites for your OS

## Clone & run

```bash
git clone https://github.com/udhawan97/Golavo.git
cd Golavo
cp .env.example .env      # optional; every key is optional
make setup                # install core + server + ui dev dependencies
make dev                  # FastAPI core + Vite UI on 127.0.0.1
make test                 # run the test suite
make lint                 # ruff + mypy + eslint
```

## Repository layout

| Path | What | License |
|---|---|---|
| `core/` | Python modeling library | Apache-2.0 |
| `server/` | FastAPI app | AGPL-3.0 |
| `ui/` | React + TypeScript + Vite | AGPL-3.0 |
| `desktop/` | Tauri 2 shell (Phase 4) | AGPL-3.0 |
| `docs-site/` | this documentation site | docs |

:::note
`make` targets are placeholders during Phase 0–1 while the packages are scaffolded. See [Contributing](/Golavo/contributing/).
:::
