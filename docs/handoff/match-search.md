# Match Search + Commentator's-Notebook-for-any-game — handoff

**Base SHA:** `3c98884` (v0.2.2; tree clean at start) · **Scope:** a read-only match
search surface over every bundled CC0 fixture, plus an on-demand Commentator's Notebook
for *any* searched match — not just the handful with a precomputed one. Additive: the
sealed forecast surface, the calibration record, and the AI layer are untouched.

The headline is the on-demand notebook. Golavo already computed a source-backed notebook
for a sealed forecast (Phase 7). This makes the same deterministic engine reachable for
any of ~75k historical matches, computed at a leak-safe pre-kickoff horizon, without
sealing a forecast and without inventing a number.

## What shipped

- `core/golavo_core/ingest/match_index.py` — the index builder. `build_match_index` folds
  the selected packs into one committed Parquet + a `matches_index.meta.json` digest, and
  (martj42 only) `goalscorers.parquet` / `shootouts.parquet` / `aliases.json`.
  `default_index_packs` selects one pack per source (latest-anchored snapshot).
  `normalize` is the shared diacritic-free casefold search key.
- `python -m golavo_core index` — the CLI that (re)builds the committed index into
  `data/index/` (`core/golavo_core/cli.py`).
- `server/golavo_server/matches.py` — the read-only search + notebook module, wired into
  four GET routes in `server/golavo_server/main.py`.
- `packaging/golavo-sidecar.spec` — bundles the frozen index + side tables (~2.4 MB) so
  the desktop sidecar can search and compute notebooks offline.
- `scripts/check_license_isolation.sh` (§3, new) — asserts every `built_from[].license`
  in the committed index meta is `CC0-1.0`.
- `.github/workflows/ci.yml` — rebuilds the index and asserts byte-equality with the
  committed copy; runs the license-isolation guard.
- UI: `ui/src/views/MatchSearch.tsx` (`#/matches`) and `MatchDetail.tsx` (`#/match/{id}`),
  contract types in `ui/src/lib/contract.ts`, fetchers in `ui/src/lib/api.ts`, mock corpus
  `ui/src/mocks/matches.json`.
- Tests: `core/tests/test_match_index.py`, `server/tests/test_matches_api.py`.

## The index: provenance, dedupe, license gate

`data/index/matches_index.parquet` is a **committed, deterministic** Parquet of
**75,079 matches** — **49,505 internationals** (martj42) + **25,574 club** (the five
openfootball leagues: EPL, La Liga, Bundesliga, Serie A, Ligue 1). Verified against the
committed meta (`row_count: 75079`) and by `source_kind` value counts. Side tables
(`goalscorers.parquet`, `shootouts.parquet`) and `aliases.json` are **internationals only**
— martj42 is the only source that ships scorer/shootout/former-name data.

Three invariants make the committed bytes trustworthy:

1. **Fail-closed license gate.** Every pack's `manifest.license` must be in
   `_CLEARED_LICENSES = {"CC0-1.0"}` before a single row is read; a non-CC0 pack raises.
   The meta records each source's license under `built_from[].license`, and both
   `check_license_isolation.sh` (§3) and CI assert they are all `CC0-1.0`. **ODbL can never
   ship frozen inside the redistributed sidecar** — the gate is enforced at build time, at
   the isolation guard, and in CI.
2. **Per-pack match ids are preserved across the merge — never re-hashed.** Each source's
   `load_matches()` output keeps its own `match_id` (martj42 uses a 7-field identity,
   openfootball a 4-field one); the frames are concatenated with those ids intact.
   Re-hashing a `match_id` over the merged frame would silently corrupt the identity
   function, so the build refuses to: after concat it asserts **no `match_id` collision
   across packs** and aborts if one is found.
3. **The build is pure.** No wall clock, sorted keys, `mergesort` — two builds of the same
   packs produce **byte-identical** Parquet and an identical `parquet_sha256`. CI rebuilds
   from the CC0 packs and diffs the sha256 against the committed copy; a mismatch means
   either the packs changed or the build changed the bytes — in both cases the fix is
   `python -m golavo_core index` + recommit `data/index/*`. `default_index_packs` keeps the
   latest-anchored snapshot per source, so a pack refresh is a deterministic re-selection.

## Server endpoints (all GET, token-gated, read-only)

Everything reads the frozen index and **never writes**. `pandas`/`pyarrow` are imported
*inside* the functions so the frozen sidecar's `/health` readiness stays fast (the first
search pays the ~25 s import; the sidecar warms it in the background).

| Route | Behaviour |
|---|---|
| `GET /api/v1/matches/search?q=&competition=&status=&limit=&offset=` | Substring + alias search over the pre-folded `home_norm`/`away_norm`/`competition` columns. `q` < 2 chars → **422**. Index missing/unreadable → **503** (`MatchIndexUnavailable`, fails closed). Ranking: team-name **prefix** hits first, then kickoff desc, then `match_id` — fully deterministic. `limit` clamped to `[1,100]`. |
| `GET /api/v1/matches/competitions` | Distinct `(competition, source_kind)` with match counts, deterministically ordered. Declared **before** `/{match_id}` so `"competitions"` is never swallowed as an id. |
| `GET /api/v1/matches/{match_id}` | One `MatchRow` + `linked_by: "match_id" \| "fixture" \| null`. Unknown id → **404**. |
| `GET /api/v1/matches/{match_id}/notebook` | The Commentator's Notebook (see below). Unknown id → **404**; a build failure fails closed to an honest empty envelope, **never a 500**. |

**`status` is derived from `is_complete`, never `kickoff < now`.** martj42's kickoff is a
midnight-UTC **day proxy** (the source has dates, not times), so a past midnight-UTC stamp
does not mean the match was played. `status=played` filters `is_complete`; `status=upcoming`
requires `~is_complete AND kickoff >= now`. The UI badge classifies the same way — a past
kickoff with no recorded score reads honestly as **"Result not in snapshot"**, never a
fabricated "Played"/"Upcoming".

### Match ↔ forecast linking — the sample-mode invariant

Linking scans the **real ledger only** (`ARTIFACT_DIR`), by `match_id` first then a
`(date, home_norm, away_norm)` fixture fallback. Two deliberate properties:

- **Samples can never masquerade as real seals.** The route passes the real ledger dir,
  never the synthetic sample fallback, so a sample `fa_*.json` id can never attach to a
  real fixture. (On a fresh desktop install the *Matchday* view shows samples; the *match
  directory* never links them.)
- **Linking is navigation, not verification.** `artifact_links` is a cheap `json.loads`
  scan with **no** integrity check — the forecast route still recomputes each artifact's
  content-addressed identity (H1) when it actually serves it. Corrupt files are skipped.

## The on-demand Commentator's Notebook (the headline)

`match_notebook` prefers a **precomputed** `notebooks/<artifact_id>.json` beside a sealed
forecast — byte-for-byte the horizon that forecast trained to (`computed: "precomputed"`).
Otherwise it computes one **on demand** (`computed: "on_demand"`) via `build_notebook()`.

**Leak-safety proof.** The on-demand `as_of = kickoff − 1s` — the *same* conservative cutoff
`seal_forecast` uses. So the notebook never sees the fixture's own result or any later
match: it is computed as if standing one second before kickoff, exactly where an honest
pre-match seal stands. There is a test for the horizon, and it was confirmed on the real
75k-row index. The internationals scorer/shootout templates only run when the side tables
load (`source_kind == "international"`); a missing side table means those templates simply
don't fire — no data is invented.

### The one deliberate tradeoff: pack-free → on-demand

Before this, the sidecar was strictly *"pack-free at runtime"* — it served only precomputed
artifacts. Computing a notebook on demand means the frozen index **is** read at runtime.
That is the single tradeoff, and it is bounded:

- **Read-only in the write sense.** `build_notebook` writes nothing; the facts package's
  **no-write invariant is AST-enforced** (Phase 7). No notebook code path can change a
  probability, forecast, or calibration number.
- **The engine still owns every number.** Facts carry their sample, denominator, base rate,
  source ids, and freshness; coincidences stay capped and quarantined.
- **The precomputed forecast path is untouched.** `/forecasts/{id}/facts` and the sealed
  surface behave exactly as before.

## Known gaps (honest)

- **No future fixtures in the vendored packs today.** The bundled packs are historical
  completed matches, so `status=upcoming` (which requires `kickoff >= now`) returns **empty**
  until a pack refresh adds scheduled fixtures. This is a data-state gap, not a bug — the
  filter logic is correct and tested; there is simply nothing forward-dated to match. A
  future pack with scheduled fixtures lights it up with no code change.
- **Load-more and the past-incomplete state are code-verified, not data-verified in mock.**
  The mock corpus (`ui/src/mocks/matches.json`) is a small synthetic contract fixture, so
  the Load-more pagination path and the "past kickoff, no recorded score" (`Result not in
  snapshot`) UI state are exercised by their code paths and by the server tests over a
  fixture index, but not visibly reproduced from the mock alone.
- **Seal-from-UI is deferred.** The API stays all-GET. A future match with no seal says so
  honestly ("Sealing from inside the app lands in a future release; today, seals are written
  by the engine CLI"), and club matches are additionally noted as historical-backtest-only
  (forward sealing currently covers internationals).

## Reproduce

```bash
python -m golavo_core index          # rebuild data/index/* from the CC0 packs
bash scripts/check_license_isolation.sh
pytest core/tests/test_match_index.py server/tests/test_matches_api.py -q
cd ui && npm ci && npm run build     # tsc --noEmit + vite build
```
