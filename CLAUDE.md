# Golavo

Local-first, provenance-bearing football forecaster. Python core + FastAPI sidecar + React UI in a Tauri shell.
Read [CONTEXT.md](CONTEXT.md) first — it defines the domain words (pack, snapshot, seal, settlement, name fold, leak-safe cutoff) that the code is named after.

## Commands

```bash
make setup        # pip install -e core[dev] + server[dev]; npm install in ui/ and docs-site/
make dev          # python scripts/dev.py — FastAPI + Vite together
make test         # pytest -q  (~840 tests across core/, server/, scripts/)
make lint         # ruff check .  +  cd ui && oxlint
make validate     # 7 validate_*.py scripts + pytest scripts/tests/test_contract_versions.py
make index        # rebuild the committed match index — see "Determinism" below
make build        # ui + docs-site production builds
```

Single test: `pytest -q server/tests/test_matches_api.py::test_name`.
UI: `cd ui && npm test` (vitest, unit) — `npm run test:e2e` (Playwright) — `npm run typecheck`.

mypy is a declared dev dep in both pyprojects but has no config file, no `[tool.mypy]` section, and no invocation — don't assume type checking runs on the Python side. `npm run typecheck` (`tsc --noEmit`, strict) is the TS gate.

**The UI linter is oxlint, not ESLint, and that is deliberate.** `ui/` is on TypeScript 7, and no release of `typescript-eslint` supports it — the latest and its canary both cap the peer at `<6.1.0`, and installing anyway crashes in `typescript-estree` reading `ts.ModuleKind.Cjs`, which TS 7 no longer exposes. oxlint parses TypeScript itself with no dependency on the TS compiler API, so it works today. Config is `ui/.oxlintrc.json`; rule names mirror ESLint's (`react-hooks/exhaustive-deps`, `typescript/no-unused-vars`). Revisit if typescript-eslint ships TS 7 support.

Lint runs `--deny-warnings`, so **any** warning fails the build — there is no backlog to hide in. `npm run lint:fix` handles the autofixable ones.

Two rules are scoped off in `ui/.oxlintrc.json` rather than obeyed, each with the reason inline (the file is JSONC — comments parse, but `$comment` is a hard error): `exhaustive-deps` in `lib/hooks.ts`, whose `useAsync` takes the caller's dep array and so can never pass an array literal, and `no-did-update-set-state` in `ErrorBoundary.tsx`, where resetting on a prop change is the point (and is now covered by `ErrorBoundary.test.tsx`). **oxlint honours no inline `eslint-disable` comment for these rules** — file-scoped config is the only lever, so a suppression costs you the rule across the whole file. Prefer restructuring: hoisting `const { refresh } = controller` or a `run?.run_id` into a local satisfies `exhaustive-deps` honestly, and depending on the object instead would have re-run those effects every render.

## Layout

| Path | What |
|---|---|
| `core/golavo_core/` | Modeling library. CLI at `cli.py` (`python -m golavo_core <ingest\|index\|evaluate\|seal\|score\|void\|notebook>`) |
| `core/golavo_core/facts/` | Templated fact engine; `guardrails.py` + `invariant.py` are the honesty core |
| `core/golavo_core/ai/` | `whitelist.py` is the numeric guard — AI prose may only contain numbers resolvable to evidence |
| `server/golavo_server/` | FastAPI. **All ~97 routes live in one 2760-line `main.py`**; siblings are services it imports |
| `ui/src/` | React 18 + Vite. `lib/contract.ts` is a hand-written mirror of `docs/contracts/` |
| `desktop/src-tauri/` | Tauri 2 shell: spawns the frozen sidecar on a random port with a per-launch token |
| `packs/` | Vendored, hash-pinned upstream data. Never edit bytes by hand |
| `data/index/` | Build output, committed. Never hand-edit |
| `docs/contracts/` | 29 JSON Schemas — the declared canon |
| `docs/adr/` | ADRs 0001, 0004–0009 (0002/0003 don't exist) |

## The five non-negotiables

From CONTRIBUTING.md — CI enforces most of them:

1. The statistical engine owns every probability. UI/docs/AI never invent or adjust a number.
2. Every displayed fact carries a source id.
3. Only CC0/CC-BY data in the repo. Never commit proprietary, scraped, or user data.
4. **ODbL stays isolated.** OpenLigaDB lives in its own pack and its own DB file. Joining it into the CC0 warehouse would trigger share-alike on the whole dataset.
5. Not a betting product. No odds, "value", "units", "locks", bankroll advice, or affiliate links — in code, copy, or docs.

## Gotchas

**Determinism is a CI gate, not an aspiration.** CI rebuilds the index and asserts
`sha256(rebuilt) == sha256(data/index/matches_index.parquet) == meta["parquet_sha256"]`.
This is why `core/pyproject.toml` pins deps with `==` (pyarrow, pandas, numpy, scipy) — a dep bump can change Parquet encoding bytes. **Bump a core dep → run `make index` → commit `data/index/*`.**

**Server caches leak across tests.** Eleven server modules expose `reset_cache()` (`matches`, `analysis`, `analytics`, `ratings`, `scorers`, `outlook`, `retrospective`, `conditions`, `context_registry`, `correction_policy`, `research/policy`). A new server test that points one of them at a tmp fixture **without an `@pytest.fixture(autouse=True)` reset will pass alone and fail in suite order.** Copy the pattern at the top of `server/tests/test_matches_api.py`. `matches` is the one exception: its index cache records the `(index, meta)` pair it was read from and retires itself — and its derivatives — when those move, so repointing `matches.INDEX_PATH` needs no reset. `reset_cache()` there now only forces a re-read of the *same* path. There is only one conftest in the repo (`scripts/tests/conftest.py`, sys.path only) — no shared fixtures.

**Contract versions are declared in three places** and cross-checked by `scripts/tests/test_contract_versions.py`: the JSON Schema, a Python constant the sidecar stamps, and a constant in `ui/src/lib/contract.ts`. Its `OWNERS` table must list every schema — **adding a file to `docs/contracts/` fails CI until you register its owners.** There is no codegen; `contract.ts` is maintained by hand and drift is caught by `server/tests/test_contract_drift.py`.

**UI test split is load-bearing.** `ui/vite.config.ts` restricts vitest to `src/**/*.test.{ts,tsx}` and excludes `tests/**`. Specs in `ui/tests/*.spec.ts` run under Playwright only. A test placed in the wrong **directory** still silently never runs — this bit once already: the glob was `*.test.ts`, so `ProgrammePullNumber.test.tsx` sat uncollected and had never run.

**Component tests render to a string, not a DOM.** The convention is `createElement` + `renderToStaticMarkup` from `react-dom/server`, asserting on HTML — no jsdom, node environment. That does not work for anything needing state, effects, or error boundaries, which only engage on a client render. For those, opt in per file with a `// @vitest-environment jsdom` docblock and drive a real root (`ErrorBoundary.test.tsx` is the worked example). Don't set jsdom globally — 37 files currently run in node and don't need it.

**Generations use an atomic pointer swap** (ADR-0004, `server/golavo_server/refresh_state.py`): write tempfile → `os.replace` → fsync dir. `active_generation()` falls back to the previous generation if verification fails. Refresh only exists when `GOLAVO_DATA_DIR` is set; source/CI mode uses the committed index.

**Cache epochs guard against stale publishes.** `IndexSnapshot` carries `frame/fingerprint/epoch` so work started on an older generation can't publish into the cache after a refresh repoints the module globals in `server/golavo_server/matches.py`.

**License isolation is AST-enforced, not grepped.** `scripts/validate_license_isolation.py` parses imports: the four `openligadb_*.py` modules may not import `golavo_core` or the core server services. `core/` may not import `overlay_odbl`; `fjelstul` (CC-BY-SA) may not appear in `core/golavo_core/ingest`. This constrains where you may put an import.

**Some routes are unusable in source mode.** `/api/v1/corrections*` and `/api/v1/research/*` hard-403 when `GOLAVO_TOKEN` is unset.

**`calibration` is imported lazily inside its handler** — numpy/pandas/scipy cost ~25s from the frozen sidecar and would block `/health`.

Env vars (all seven): `GOLAVO_TOKEN`, `GOLAVO_DATA_DIR`, `GOLAVO_HOST`, `GOLAVO_PORT`, `GOLAVO_PARENT_PID`, `GOLAVO_SOURCE_SHA`, `GOLAVO_NO_RESEARCH`.

## Generated files — regenerate, don't edit

| File | Regenerate with |
|---|---|
| `data/index/*` | `make index` |
| `data/context/manifest.json` | `scripts/build_context_manifest.py` |
| `data/enrichment/*` | `scripts/build_geo_enrichment.py` |
| `data/fixtures/sample_artifacts/` | `scripts/generate_sample_artifacts.py` |
| `THIRD_PARTY_NOTICES.md` | `scripts/gen_third_party_notices.py` |
| version strings repo-wide | `make release-bump VERSION=x.y.z` |

`data/sources/registry.json` is the exception — hand-maintained canon, validated against pack manifests by `scripts/validate_sources.py`.

## CI jobs that must be green

`core` (ruff + 5 validators + notices check + index determinism + pytest) · `ui` (oxlint + vitest + build + Playwright) · `docs` (`astro check` + build) · `desktop-check` (`cargo test --locked`, macOS only — so the one `#[cfg(windows)]` test never compiles in CI) · `license-isolation` · `sidecar-smoke` (PyInstaller on macOS + Windows, `--version` and `--smoke` must exit 0).

## Conventions

- Conventional Commits (`feat(models): …`), sign off with `git commit -s`.
- Any model change needs a backtest and its effect on RPS / log loss.
- Docs-site: `astro.config.mjs` sets `base: "/Golavo"`; the sidebar is hand-authored, so a new page needs a sidebar entry. `tokens.css` must load before `custom.css`.
