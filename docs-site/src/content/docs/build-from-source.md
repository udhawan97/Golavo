---
title: Build from source
description: Prerequisites and commands to run Golavo locally as it's being built.
---

## Prerequisites

- **Python** 3.12+ (the core pins `scipy==1.18.0`, which requires 3.12)
- **Node** 22+
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
| `server/` | FastAPI app | Apache-2.0 |
| `ui/` | React + TypeScript + Vite | Apache-2.0 |
| `desktop/` | Tauri 2 shell (Phase 4) | Apache-2.0 |
| `docs-site/` | this documentation site | docs |

:::note
The `make` targets (`setup`, `dev`, `test`, `lint`, `validate`, `build`) are live. `make validate` runs provenance + artifact checks; `make build` builds the UI and docs site. See [Contributing](/Golavo/contributing/).
:::
