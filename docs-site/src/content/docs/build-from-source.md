---
title: Build from source
description: Run Golavo locally in your browser from a source checkout.
---

## Prerequisites

- **Python** 3.12+ (the core pins `scipy==1.18.0`, which requires 3.12)
- **Node** 22+
- (Phase 4 only) **Rust** stable + the Tauri prerequisites for your OS

## Clone & run in your browser

```bash
git clone https://github.com/udhawan97/Golavo.git
cd Golavo
cp .env.example .env      # optional; every key is optional
make setup                # install core + server + ui dev dependencies
make dev                  # starts both services and opens 127.0.0.1:5173
make test                 # run the test suite
make lint                 # ruff + mypy + eslint
```

`make dev` keeps the FastAPI service on `127.0.0.1:8000`, points the Vite UI at
that local service, and opens `http://127.0.0.1:5173`. Press `Ctrl+C` to stop both.
Use `python scripts/dev.py --no-open` when you do not want a browser tab opened
automatically.

### Windows PowerShell without `make`

```powershell
git clone https://github.com/udhawan97/Golavo.git
Set-Location Golavo
Copy-Item .env.example .env
python -m pip install -e "core[dev]" -e "server[dev]"
npm --prefix ui install
python scripts/dev.py
```

The Python launcher automatically uses `npm.cmd` on Windows and stops both services
when you press `Ctrl+C`. Git Bash or WSL can use the shorter `make setup` / `make dev`
path above.

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
