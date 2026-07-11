# Golavo Phase 1 plan & lane prompts

## Where we are

**Phase 0 is landed on `main`** (merge `ba86a48`), CI green. Both lanes integrated:

- **Codex core** (`479f6fa`, `5234d63`): CC0 martj42 sourcepack pinned at upstream `ddd7249a`, typed ingest, five deterministic candidates (climatological, Elo ordinal-logit, independent Poisson, time-decayed Dixon-Coles, bivariate Poisson), chronological WC2022/EURO2024/WC2026 evaluation (log loss primary), immutable seal/score CLI, read-only FastAPI, provenance + schema CI. **Elo beats the climatological baseline on log loss on all three folds; no model is called a champion.**
- **Claude UI** (`#12`, `#13`): the Forecast Audit Workbench (`ui/`), mock-driven, consuming the frozen `ForecastArtifact` 0.1.0 contract.

Phase 0 exit gates are met. Verified twice locally (11 tests, provenance, 8 artifacts schema-valid, ruff) plus green main CI.

## Phase 1 goal

Decide **club coverage** honestly, and make the UI show **real** forecasts. Two independent lanes, same proven collision-free split (backend/docs vs `ui/`).

**The crux is a gate, not a feature.** Club coverage is only claimed/shipped if a lawful open source survives an audit. The default open club candidate is **openfootball** (CC0). Prior research flagged its freshness as *season-lag* (not necessarily current mid-season) — so the audit may legitimately **fail** the "current" criterion. If it does, club coverage stays **historical-only** or internationals-only; we do **not** overclaim. That honest outcome is a success for Phase 1.

## Carryover gaps from Phase 0 (do not silently inherit as solved)

- Kickoff time is a `00:00:00Z` proxy (martj42 has dates, not times); seals use an earlier timestamp. Replace only if a lawful kickoff-time source lands.
- WC2026 fold is a partial-window report; regenerate from a freshly pinned pack after completion.
- Audit trail is append-only JSONL, **not** hash-chained (deferred per ADR-0001; keep append-only for Phase 1 unless a concrete multi-party verification need appears).
- No accepted source for club lineups/xG/corners/injuries. Rejected provenance-laundering datasets get no adapters.

## Lane split (unchanged; conflict-free)

- **Codex:** `core/`, `server/`, `packs/`, `data/`, `scripts/`, `docs/`, `.github/`, root shared files, and markdown-content corrections in `docs-site/src/content/docs/**`. Owns the canonical schema (`docs/contracts/forecast_artifact.schema.json`) — bump only additively (0.1.0 → 0.2.0) and record it in the handoff.
- **Claude:** `ui/**` only.
- **Merge order:** Codex first, Claude rebases and merges second.
- **Verify twice, then merge and push to `main`** (standing rule): run tests/build/lint, run them again, only then land.

---

## Prompt for Codex (Phase 1)

```
You are implementing Phase 1 of Golavo. Phase 0 is merged on main (commit
ba86a48): a lawful CC0 internationals backbone (martj42), five deterministic
model candidates, chronological evaluation (log loss primary), an immutable
seal/score CLI, a read-only FastAPI, and provenance + schema CI. You own the
BACKEND, DATA/PROVENANCE, CONTRACT, CI, DOCS. A separate agent owns ui/ — never
edit ui/.

FIRST ACTIONS: git checkout main; git pull; git rev-parse --short HEAD (record
as BASE_SHA; expect ba86a48 or later); git status --porcelain (must be clean);
git checkout -b lane/codex-phase1.

ALLOWED: core/**, server/**, packs/**, data/**, scripts/**, docs/**, .github/**,
README.md, NOTICE, CHANGELOG.md, CONTRIBUTING.md, Makefile, ruff.toml,
docs-site/src/content/docs/** (markdown content only).
FORBIDDEN: ui/**, assets/**, docs-site/src/styles/**, docs-site/astro.config.mjs,
docs-site/package*.json, LICENSE*.

THE GATE (do this first, and let it fail honestly):
1) Add packs/openfootball/ via scripts/build_sourcepack.py extended for
   github.com/openfootball/football.json (CC0): vendor a pinned snapshot
   (record upstream commit SHA), manifest.json with per-file sha256 + CC0 text.
2) scripts/audit_openfootball.py writing docs/handoff/openfootball-audit.md with
   an explicit PASS/FAIL per criterion:
   - FRESHNESS: is the current (2025/26) season present and recently updated?
     (report last upstream commit date; PASS only if in-season current.)
   - COMPLETENESS: for a sampled completed season (e.g. 2024/25 Premier League),
     are all 380 matches present with full-time scores? (PASS >= 99%.)
   - CORRECTNESS: spot-check 30 sampled results against a second CC0 source or
     martj42 where competitions overlap; report mismatch rate (PASS < 2%).
   The gate decides scope: if FRESHNESS fails but COMPLETENESS/CORRECTNESS pass,
   club coverage is HISTORICAL-ONLY (completed seasons); if COMPLETENESS or
   CORRECTNESS fail, club coverage is REJECTED and you stay internationals-only.
   Do NOT force a pass. Document the real result.

IF (and only if) the audit permits club coverage:
3) Extend core ingest + the five candidates to ONE club competition (English
   Premier League) as a second backbone; run the SAME chronological evaluation
   (log loss primary, Brier, ECE, reliability bins, RPS) over completed seasons
   only; emit docs/handoff/eval_report_epl.md + update eval_summary.json (add
   folds; keep the internationals folds). Reuse the seal/score CLI unchanged.
   Report honestly which candidates beat Elo; crown nothing.
4) Add a real-fixture seal demonstration: seal one upcoming/most-recent fixture
   from a freshly pinned pack via the CLI; store the artifact in
   data/fixtures/sample_artifacts/ (schema-valid); note it is a real seal, not a
   synthetic fixture (real code_git_sha).

ALWAYS:
5) Keep provenance + schema validation green in CI; add the openfootball pack to
   the provenance check. Contract stays 0.1.0 unless a field is genuinely needed
   — if so, bump to 0.2.0 ADDITIVELY (no breaking changes) and document it in the
   handoff for the UI lane.
6) DOCS: update docs-site data/coverage.md + data/sources.md and README coverage
   to reflect the AUDIT RESULT exactly (historical-only / rejected / internationals-
   only). No present-tense claims beyond what shipped.

ACCEPTANCE (all before PR): pytest + ruff green; provenance validates both packs;
all artifacts schema-valid; determinism + leakage tests still green; the audit
doc exists with an explicit verdict; coverage docs match the verdict.
HANDOFF: docs/handoff/codex-phase1.md — BASE_SHA, audit verdict, what shipped,
eval tables, contract version, sample-artifact paths, known gaps.
VERIFY TWICE, then open a PR to main and (after green CI) merge it FIRST.
STOP CONDITIONS: working tree dirty at start; openfootball license no longer CC0;
audit cannot be completed from primary sources; any change needing forbidden
paths; any non-additive schema change.
```

## Prompt for Claude (Phase 1)

```
You are advancing the Golavo Forecast Audit Workbench (ui/) in a fresh session.
Phase 0 shipped a mock-driven read-only UI over the frozen ForecastArtifact
0.1.0 contract, plus a real read-only backend (FastAPI). Golavo seals a
deterministic forecast BEFORE kickoff and scores it after full time; honesty and
auditability are the product. NOT a betting app — never use odds framing or the
words "locks", "value", "units", "picks".

YOU OWN ui/ ONLY. A parallel agent owns the backend/schema/docs. Do not edit
anything outside ui/.

FIRST ACTIONS: git checkout main; git pull; git rev-parse --short HEAD (record as
BASE_SHA); git status --porcelain (if ui/** dirty, STOP; dirt outside ui/ is not
yours); git checkout -b lane/claude-phase1-ui.

ALLOWED: ui/** only. FORBIDDEN: everything else (core/**, server/**, packs/**,
data/**, scripts/**, docs/**, docs-site/**, assets/**, .github/**, root files).

CONTEXT: the backend exposes (read-only, no auth, source mode):
  GET /health
  GET /api/v1/forecasts          -> ForecastArtifact[] (newest first)
  GET /api/v1/forecasts/{id}     -> ForecastArtifact
  GET /api/v1/eval/summary       -> EvalSummary
CORS allows http://127.0.0.1:5173 and http://localhost:5173. ui/src/lib/api.ts
already switches on import.meta.env.VITE_GOLAVO_API (live) vs bundled mocks.

TASKS:
1) Make the LIVE path real and robust: when VITE_GOLAVO_API is set, fetch from
   the endpoints above with proper loading / empty / error / stale states and a
   graceful fallback to mocks on failure (surface a visible "using mock data"
   badge). Never fabricate data or claim a live backend when running on mocks.
2) Add a cross-source CALIBRATION view fed by /api/v1/eval/summary: per-model log
   loss + Brier table (log loss headline), and reliability diagrams from
   reliability_bins (p_mid vs observed_rate, point size ~ n, diagonal reference).
   Handle multiple folds (internationals now; club folds may appear later).
3) Polish: keyboard nav, visible focus, WCAG 2.2 AA contrast, prefers-reduced-
   motion, tabular numerals, hashes/SHAs in monospace, one-decimal percentages.
4) Consume the contract as-is (0.1.0). If the backend advertises 0.2.0 with new
   fields, render them defensively; if a needed field is missing, note it in your
   handoff for the backend lane — do NOT invent fields or edit the schema.

ACCEPTANCE (before PR): npm install && npm run build clean; tsc --noEmit clean;
app runs at 127.0.0.1:5173 on mocks by default (no VITE_GOLAVO_API) with every
state reachable; live path verified against a running server if available, else
documented; initial JS <= 300KB gzip; no betting lexicon (grep your diff);
git diff --name-only touches ui/** only.
HANDOFF: ui/HANDOFF.md — BASE_SHA, screenshots (ui/screenshots/), which view uses
which endpoint, live-vs-mock behavior, any contract gaps as notes for the backend.
VERIFY TWICE, then open a PR to main; rebase on main and merge AFTER the backend
lane merges.
STOP CONDITIONS: any change needs files outside ui/; the contract can't express a
view's needs (document, don't invent); ui/ has uncommitted changes you didn't make;
anything would imply a live backend exists when it does not.
```
