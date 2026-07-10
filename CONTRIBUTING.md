# Contributing to Golavo

Thanks for helping build an honest football forecaster. This guide covers how the repo is laid out, how to work in it, and the non-negotiable rules that keep Golavo trustworthy and legal.

## Golden rules (read these first)

1. **The statistical engine owns every probability.** UI, docs, and the AI layer never invent, round-trip, or "adjust" a number. AI output must resolve every number to its evidence bundle or it is rejected.
2. **Every displayed fact carries a source id.** No source, no ship.
3. **Never commit proprietary or user data.** No football-data.org / API-Football responses, no StatsBomb data, no scraped feeds. Only CC0 / CC-BY sources belong in the repo, and only as small frozen demo fixtures under `data/fixtures/`.
4. **ODbL stays isolated.** OpenLigaDB (ODbL) data lives in its own pack and its own database file. Never join it into the CC0 warehouse — that would trigger share-alike on the whole dataset. CI enforces this.
5. **Golavo is not a betting product.** No odds, no "value," "units," "locks," bankroll advice, or affiliate links — in code, copy, or docs.

## Repository layout

| Path | What | License |
|---|---|---|
| `core/` | Python modeling library (ingest, warehouse, models, ledger, facts) | Apache-2.0 |
| `server/` | FastAPI app (routes, jobs, evidence bundles, AI gateway) | Apache-2.0 |
| `ui/` | React + TypeScript + Vite | Apache-2.0 |
| `desktop/` | Tauri 2 shell (Phase 4) | Apache-2.0 |
| `packs/` | data-pack build definitions (`core-cc0`, `overlay-odbl`) | per-source |
| `docs-site/` | Astro + Starlight product site | docs |
| `docs/adr/` | architecture decision records | docs |

Golavo code is licensed under Apache-2.0; data packs carry separate licenses. By contributing code or documentation you agree that contribution is licensed under Apache-2.0. Data contributions must declare their provenance and license explicitly.

## Development setup

```bash
git clone https://github.com/udhawan97/Golavo.git && cd Golavo
cp .env.example .env          # optional; Golavo runs local with no keys
make setup                    # install core + server + ui dev deps
make dev                      # run the FastAPI core + Vite UI
make test                     # run the test suite
make lint                     # ruff + mypy + eslint
```

(`make` targets are placeholders during Phase 0–1; see the `Makefile`.)

## Branches, commits, PRs

- Branch from `main`: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
- Use [Conventional Commits](https://www.conventionalcommits.org/): `feat(models): add bivariate poisson fit`.
- Sign off your commits (DCO): `git commit -s`.
- Keep PRs focused. Fill in the PR template. All CI checks must be green.
- Any change touching the model must include or update a **backtest** and note its effect on RPS / log loss. Accuracy claims need forward, out-of-sample evidence.

## Tests & quality gates

- Python: `pytest`, `ruff`, `mypy`. UI: `vitest` / `eslint`. Docs: Astro build must pass.
- Determinism test: the same snapshot set must produce a bit-identical forecast.
- Leakage audit: features may only use data with `retrieved_at ≤ seal time`.

## Reporting bugs / proposing features

Open an issue with the relevant template. Security issues: **do not** open a public issue — see [SECURITY.md](SECURITY.md).
