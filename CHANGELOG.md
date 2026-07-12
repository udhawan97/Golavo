# Changelog

All notable changes to Golavo are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.1] - 2026-07-12

Sharper commentator notes and a cleaner post-pivot flow.

### Added
- **Signature form stats in the Commentator's Notebook** — the unusual insights a
  commentator knows but most scoreboards never show, all deterministic and
  number-disciplined:
  - **both-teams-scored rate** — how often a side's recent matches see both teams
    find the net;
  - **scoring momentum** — goals a game over the last six versus the stretch
    before, surfaced only when the shift is real;
  - **clean-sheet rate** — how reliably a defence shuts the door (distinct from the
    current clean-sheet streak);
  - **head-to-head goal character** — the average goals and both-scored count in
    the meetings, the dimension the win/draw/loss record leaves out.
  Registry version bumped; these run under the same pre-registered
  multiple-comparison, sample, and freshness guards as every other fact.

### Changed
- **"Three things to know" and the Commentator's Notebook no longer overlap.** The
  headline picks are removed from the full notebook below, so the notebook is the
  deeper cut rather than a repeat — the two panels now partition the facts.
- **Post-pivot link and label cleanup.** The sealed-forecast list is titled
  "Sealed forecasts" (under Model Lab); cross-links from the ledger, backtests, and
  forecast pages point at the new `/lab/*` routes instead of the retired
  `#/ledger` and `#/eval`.

## [0.3.0] - 2026-07-12

The architecture rethink, first slice: Golavo opens on **games**, not on an audit
form, and any match can be understood at an analyst level on demand. The sealing,
provenance, calibration, and no-leakage machinery is unchanged — it moved behind
the product, where it belongs.

### Added
- **Match Cockpit — a model council for any indexed match.** Opening a match now
  computes an on-demand, leak-safe multi-model read at the seal's own
  `kickoff − 1s` cutoff:
  - a **Replay** for a played match (reconstructed with pre-kickoff data only — it
    is *not* a forecast that existed at the time, and never enters the track
    record) or a **Preview** for a scheduled one, each labelled and time-stamped;
  - **two voices** — Elo (ratings) and Dixon–Coles (goals) — shown side by side
    with whether they agree, plus a climatology **baseline** for reference. The
    Poisson variants are disclosed, never counted as extra opinions, and nothing is
    averaged into a synthetic consensus;
  - model-implied goals (labelled *expected, not predicted*), the goal model's
    coherent exact-score grid, and an honest **abstain** state when either side has
    too little history.
  New endpoint `GET /api/v1/matches/{id}/analysis` (contract 0.3.0, additive).
- **Games-first home.** The default page is now **Games**: recent results and any
  upcoming fixtures from the local index, a search entry to 75,000+ matches, and
  league shortcuts. A fresh install with an empty ledger is a full, useful page —
  offline, no account. New endpoint `GET /api/v1/matches/recent`.
- **Leagues browse hub** for the five bundled club leagues and internationals.
- **Model Lab.** Track record, Backtests, Methodologies, and the sealed-forecast
  list are consolidated under one section. The new *Methodologies* page explains,
  in plain terms, why three of the five families are really one voice.

### Changed
- **Primary navigation is now Games / Leagues / Model Lab.** The old Matchday /
  Matches / Ledger / Evaluation tabs are gone; `#/ledger` and `#/eval` redirect
  into Model Lab so existing links and exports keep working.
- **Sealing is reframed as an expert "Track this prediction" action** — the cockpit
  is the live read; sealing is how you put a pre-kickoff prediction on the record.
  The seal engine, eligibility rules, and immutability are unchanged.

### Notes
- No fabricated capabilities: live club fixtures, standings, season projections,
  and observed xG/lineups/injuries are **not** part of this release (no lawful open
  source exists for the latter as of this writing). The Match Cockpit is honest
  about what it can and cannot show.

## [0.2.6] - 2026-07-12

### Added
- **Reading comfort** (header **Aa**). A small popover for how the app *reads* —
  never what it says: theme (Light, Dark, or a new **Warm** low-blue palette for
  evening reading), text size (four steps that scale the whole app), line spacing,
  and contrast (which follows the OS "increase contrast" setting). Warm is a
  dedicated, contrast-checked palette, not a screen tint. It's for comfort, not eye
  protection, and the copy says so.
- **"Three things to know" now leads with the fact closest to the fixture** — a
  head-to-head record surfaces above a competition-wide base rate (ranked by scope,
  then specificity). Still a pure, documented pick from the notebook; never AI.
- **"What moved" on a re-seal.** When a fixture is re-sealed, the newer forecast
  shows each outcome's probability *was → now* with the change in whole points —
  line movement between two honest pre-kickoff seals, not an edit, deltas summing
  to zero.
- **Activate local AI from Settings.** A new *Local intelligence* section surfaces
  the AI Deep Read provider (Off by default; Local · Ollama / llama.cpp, or
  OpenAI / Anthropic BYOK). It only reads and cites the sealed numbers and can never
  change a probability.
- **Automated UI gate.** A Playwright + axe-core suite checks no horizontal overflow
  at mobile/tablet/desktop widths and no serious accessibility violations across all
  three themes, on every push.

### Changed
- **Probabilities read as whole numbers** in the bars and plain-language summaries
  (rounded so a 1X2 split still sums to 100), with a natural-frequency gloss ("about
  3 in 5"); one decimal survives only in the expert tables.
- **The local engine prefers a refreshed data snapshot when one is present** —
  internal groundwork toward pulling a newly-spotted fixture in so it is instantly
  forecastable (no user-facing control yet).

### Fixed
- **Header settings gear** redrawn — the previous icon's transform left it visibly
  off-centre.
- **Settings spacing** — hint text now sits with its control and wraps at a readable
  measure instead of bleeding across the panel.
- **Probability-bar labels now clear WCAG AA 4.5:1 in every theme.** The light and
  warm palettes previously dropped the dark segment labels just under the threshold;
  the bar now uses theme-independent segment colours.

## [0.2.5] - 2026-07-12

### Added
- **Redesigned match & forecast pages** — a calmer "workbench" layout: a unified
  match header, a single trust strip, plain-language insight cards, and expert
  detail tucked into collapsible drawers. Same sealed numbers, presentation only,
  now with a UI test suite (Vitest).
- **Opt-in "keep fixtures up to date"** (Settings → Data, off by default). When
  on, Golavo asks the CC0 fixture source on launch whether a new upcoming
  international match has appeared, and flags it on the Matches page. This is the
  **only** time the app reaches the network on its own — it reads only public
  fixture data and sends nothing. New read-only `GET /api/v1/fixtures/check`.

### Changed
- **Search remembers where you were.** The query, filters, and results survive
  opening a match and pressing Back (persisted in sessionStorage, not the URL),
  the empty state offers popular-search chips so the directory is browseable
  without typing, and the warming / error / load-more states now offer Retry.
- **The sidecar launch token is passed via the environment, not the command
  line**, so it is no longer visible to other local processes via `ps`; the
  sidecar also refuses to bind a non-loopback host. Verified end-to-end on a real
  desktop build — the auth gate enforces the env-delivered token.

### Fixed
- **SECURITY.md corrected in both directions.** In-app updates are cryptographically
  signed and verified against a pinned public key (not "planned/gated on secrets");
  and the claimed logging-redaction filter, backup/verify migrations layer, and
  local crash reporting were removed — none of those mechanisms exist. The
  deterministic fact engine is no longer listed as planned.

## [0.2.4] - 2026-07-12

### Added
- **Generate a forecast from inside the app — no CLI.** A new write route
  `POST /api/v1/matches/{match_id}/seal` runs the same deterministic engine as
  `golavo seal` (byte-identical) and persists an immutable artifact; `GET
  /api/v1/matches/{match_id}` now carries a typed `seal_eligibility` verdict. The
  match page shows a **Generate local forecast** button for an eligible fixture,
  and an honest, reason-specific message otherwise (already played, seal window
  closed, internationals-only, pack unavailable). Forward seals cover men's senior
  internationals — the only source that maps to one pinned CC0 pack. The client
  supplies only a match id and optional model family; the pack, training date, and
  as-of are all resolved server-side, so a seal cannot be backdated or pointed at
  an untrusted pack. Idempotent per (fixture, family), and it runs off the event
  loop so a slow seal never freezes the rest of the API. **The desktop build now
  bundles the internationals pack**, so sealing works in the installed app — the
  `--smoke` probe fails the build if the pack is missing.
- **Outcome & goal summaries on the forecast page.** Exact re-buckets of the
  sealed score distribution — double chance, total-goal thresholds, and the
  total-goals distribution — computed as true marginals of the same grid, so they
  reconcile with the 1X2 and score numbers by construction. Analysis language
  only; markets whose tail isn't exactly recoverable (both-teams-to-score, clean
  sheets, per-team totals) are deliberately omitted.
- **Match Search + a Commentator's Notebook for any game.** A new read-only search
  surface over a committed, deterministic Parquet index of **75,079 matches**
  (**49,505 internationals** from martj42 + **25,574 club** from the five openfootball
  leagues — EPL, La Liga, Bundesliga, Serie A, Ligue 1), built by
  `python -m golavo_core index`. Four GET, token-gated, read-only endpoints:
  `GET /api/v1/matches/search` (`q` < 2 chars → 422; index missing → 503;
  `status` ∈ `played|upcoming` derived from `is_complete`, never a midnight-UTC
  day-proxy kickoff), `/matches/competitions`, `/matches/{id}`
  (`linked_by: "match_id"|"fixture"|null`), and `/matches/{id}/notebook`.
  - **A Commentator's Notebook for *any* searched match.** A match without a precomputed
    notebook gets one computed **on demand** at `as_of = kickoff − 1s` — the same
    conservative horizon `seal_forecast` uses — so it can never read the fixture's own
    result or any later match (leak-safe; tested and confirmed on the real index). A
    sealed match with a precomputed notebook serves that instead
    (`computed: "precomputed"` vs `"on_demand"`). This is the one deliberate tradeoff:
    the sidecar now reads the frozen index at runtime, but it stays read-only in the
    write sense (`build_notebook` writes nothing; the facts no-write invariant is
    AST-enforced), the engine still owns every number, and the precomputed
    `/forecasts/{id}/facts` path is untouched.
  - **Sample forecasts can never masquerade as real seals.** Match ↔ forecast linking
    scans the **real ledger only** (`ARTIFACT_DIR`), by `match_id` then a
    `(date, home, away)` fallback, so a synthetic sample id can never attach to a real
    match. Linking is cheap navigation (no integrity check); the forecast route still
    recomputes each artifact's content-addressed identity on serve.
  - **License gate — ODbL can never ship in the sidecar.** The index builder fails closed
    unless every source pack is `CC0-1.0`, and both `check_license_isolation.sh` and CI
    assert the committed index's `built_from` licenses are all CC0. Per-pack `match_id`s
    are preserved across the merge (never re-hashed over the combined frame), a
    cross-pack collision aborts the build, and CI rebuilds the index and asserts
    byte-equality with the committed copy (`parquet_sha256`) — a drift means "rebuild +
    recommit". The frozen index + side tables (~2.4 MB) are bundled into the desktop
    sidecar.
  - **UI:** a `/matches` search view (debounced, grouped internationals/club, filters,
    honest badge states incl. "Result not in snapshot") and a `/match/{id}` detail with
    four forecast states (sealed → link; played → "Golavo never retro-forecasts a played
    match"; future → "sealing from inside the app lands in a future release", club-gated
    to note historical-backtest-only; not-found → search) plus an always-on Commentator's
    Notebook block. Nav entry, header search icon, and a sample-banner CTA.
    **Seal-from-UI is deferred — the API stays all-GET.**
  - **Quick wins:** Matchday + Ledger client-side filters; an AI Deep Read sample-mode
    note; Eval ↔ Ledger cross-links; a Settings footer link; not-found → search.
  - Known gap: the vendored packs are historical, so `status=upcoming` (an unplayed
    fixture kicking off today or later) is **empty until a pack refresh** adds
    scheduled fixtures — likewise, in-app sealing has nothing in-window to seal
    until then, and reports a typed `kickoff_passed`/`pack`-scoped reason honestly.
  - See [`docs/handoff/match-search.md`](docs/handoff/match-search.md).

### Fixed
- **Search: multi-word queries and match-day fixtures.** Search now tokenizes the
  query and requires every term to appear (in either team name or the
  competition), so "argentina switzerland" resolves to that fixture instead of
  returning nothing; multi-word former-name aliases (e.g. "soviet union" → Russia)
  still resolve. `status=upcoming` now measures from the start of today (UTC)
  rather than `now`, so a fixture stays listed through its own match day instead
  of vanishing at the midnight-UTC day-proxy kickoff.
- **Ledger writes are crash-safe.** Artifacts are written atomically (temp file +
  rename) under a lock, a truncated file left by a killed process is repaired
  rather than permanently blocking that fixture's id, and scoring/voiding now
  integrity-verify the input seal before writing a successor.
- **Frozen sidecar: on-demand Commentator's Notebooks were always empty (desktop
  regression in 0.2.3).** The PyInstaller spec bundled only three of the four
  runtime contract schemas — `docs/contracts/facts.schema.json` was missing — so
  in the installed app `build_notebook(validate=True)` raised on the schema read
  and `GET /api/v1/matches/{id}/notebook` failed closed to `available: false`
  for every match without a precomputed notebook. Source mode was unaffected,
  which is why tests and dev runs never saw it. Three-layer fix: the spec now
  bundles `facts.schema.json`; the sidecar `--smoke` probe additionally requests
  one real on-demand notebook and fails unless `available: true` (so a dropped
  `docs/contracts` datas entry fails CI's sidecar-smoke job instead of
  shipping); and a unit test asserts every `*schema_path` resolver target in
  `golavo_core.resources` is listed in the spec datas, catching the omission at
  PR time in source mode.

## [0.2.3] - 2026-07-11

### Added
- **Entertaining startup screen.** The loading splash now shows a live progress
  bar with a status line ("Unpacking the forecasting engine…" → "Warming up the
  models…" → "Almost ready…") and a rotating deck of genuinely-true, genuinely-
  obscure football facts, so the ~30-40s first-launch unpack passes with
  something to read instead of a bare spinner. The progress bar eases toward
  ~94% and lets the app itself take over the moment the engine is ready — it
  never claims to be finished before it is. Both themes, reduced-motion aware.

## [0.2.2] - 2026-07-11

**Desktop first-run UX fixes.** Two problems a fresh desktop install hit:
a ~30-40s blank window while the engine unpacked (felt broken, no feedback),
and an empty Matchday (the sidecar read the empty per-user ledger instead of
showing anything).

### Fixed
- **Instant window + honest loading state.** The window now opens
  **immediately** with a "Starting the local engine…" splash instead of
  ~30-40s of blank screen — the health gate moved off the main thread and the
  UI holds behind the splash until a `backend://ready` signal (or a `/health`
  poll). Time-to-window measured ~2-3s (was ~45s).
- **Sample forecasts on a fresh install.** The desktop app now **shows the 8
  bundled synthetic sample forecasts** when the ledger is empty, labelled
  honestly — a "Sample data" badge and a first-run banner, driven by a new
  `GET /api/v1/meta` (`forecast_source: sample|ledger`). Samples never reach
  the forward calibration record (that always reads the real ledger), a lone
  corrupt seal no longer blanks Matchday, and the post-update "Updated to X"
  toast is re-checked after the (now background-thread) finalize so it isn't
  missed. The badge stays neutral until the source resolves rather than
  flashing "Live" over synthetic data.

Two independent review loops (four adversarial passes) ran over this change;
all findings closed and verified before release.

## [0.2.1] - 2026-07-11

**First updater-enabled release.** Installs of v0.2.1 and later update themselves
in-app (consent-first, signature-verified, ledger backed up before install).
v0.1.0 and v0.2.0 predate the updater — update from them with one manual
download; it's in-app from then on. macOS fatal-launch dialog now blocks via
osascript (the pre-event-loop rfd path flashed and orphaned the window); two
adversarial review loops plus an install/no-crash verification hardened the
whole flow.

### Fixed
- Harden the read-only forecast list against a schema-broken artifact on disk: a
  `jsonschema.ValidationError` (not a `ValueError`) is now caught alongside the
  other bad-artifact errors, so one corrupt `fa_*.json` is omitted rather than
  failing the whole `/api/v1/forecasts` request. Follow-up to H1.
- **Windows sidecar watchdog: pinned-handle rewrite (extends v0.2.0's H3).**
  The `--parent-pid` probe's `os.kill(pid, 0)` was worse than H3 described:
  CPython maps signal 0 through to `TerminateProcess`, so the probe KILLED the
  desktop shell ~1s after boot rather than merely erroring. This replaces the
  H3 probe with a test-covered implementation: `OpenProcess` + zero-timeout
  wait, a pinned parent handle on Windows (immune to PID reuse), probe errors
  treated as parent-gone, and unit tests for both platform branches.

### Added
- **In-app updates (desktop).** Golavo now updates itself — no git, no
  terminal. Consent-first: a one-time card asks before any update check ever
  leaves the machine (the "no runtime network call unless you opt in" promise
  holds); enabled, the app checks GitHub once a day and shortly after launch.
  The flow is staged and explicit — passive header pill → Software Update
  sheet (release notes, **Update now** / **Skip this version** / **Later**) →
  event-driven progress bar with a working Cancel → platform-true install
  ("Restart Golavo" on macOS, "Quit & install" on Windows, which reopens
  itself). Every download is **cryptographically verified** against the
  public key compiled into the app before installing (the updater keypair now
  exists; CI signs every release artifact). The ledger is backed up
  immediately before install, and the backup has a real lifecycle: armed only
  until the new version's first healthy boot (then retired), restored with a
  native explanation dialog if that boot fails — never restorable twice, and
  never months later over newer data. A new **Settings** page (header gear)
  shows the version, auto-check toggle, last-checked time, manual **Check
  now**, skip management, and the record of the last verified update; the
  post-update toast only claims "ledger backed up" when one truly was.
  Source/dev builds show honest "update via git / releases" copy instead of
  dead controls. New sidecar route `POST /api/v1/shutdown` (token-gated,
  desktop-only) lets the shell stop the whole sidecar tree before the Windows
  installer runs. Local E2E harness: `scripts/test-updater-local.sh`.

### Changed
- **Release pipeline hardened for updates.** Stable `v*` releases now publish
  as real (non-pre-) releases so the update endpoint resolves; the release is
  a draft until every asset — installers, signatures, and the new
  `latest.json` update manifest — is uploaded, then flips live atomically.
  The manifest uses installer-specific Windows keys (`windows-x86_64-nsis` /
  `-msi`) so an MSI install is never "updated" by the NSIS installer. CI
  hard-fails a tag whose version doesn't match the committed one
  (`make release-bump VERSION=x.y.z` syncs all 11 spots via
  `scripts/bump_version.py`), a stable tag without the signing secret, a
  placeholder pubkey, and a half-built platform matrix.

## [0.2.0] - 2026-07-11

**Hardening capstone.** An adversarial self-review of the shipped v0.1.0 product
(see [`docs/handoff/v0.2-review.md`](docs/handoff/v0.2-review.md)) found **no
Critical** defects and **three High** findings — each fixed below with a
regression test. Determinism, the AI numeric whitelist, key isolation, and the
model coherence guarantees held under scrutiny. This release also folds in the
Phase 7–8 work (Fact & Coincidence engine; exact-score matrix + Casual/Expert)
that accumulated after the v0.1.0 tag.

### Security
- **Artifact integrity is now verified on every read path (H1).** The read-only
  API and the calibration aggregator recompute each artifact's `payload_sha256`
  and content-addressed `artifact_id` before use (`verify_artifact_integrity` /
  `load_verified_artifact`), not just schema + coherence. A hand-edited or swapped
  `fa_*.json` is omitted from the forecast list and refused (HTTP 500) on direct
  fetch, and can no longer skew the public calibration record. Previously the serve
  path trusted on-disk JSON, so the "coherence enforced on every load / immutable,
  auditable" guarantee held only on the write path.
- **Pack-integrity claims corrected to match the code (H2).** `SECURITY.md`,
  `packs/README.md`, and `README.md` described data/model packs as **minisign
  signature-verified against a pinned public key** with an "unsigned packs require
  override" control — none of which exists (only per-file SHA-256 self-hashing).
  Reworded to the true mechanism (hash-verified corruption-detection) and marked
  signature verification **planned (ADR-0001), not yet implemented**. The release
  workflow's checksum-"signing" step was a no-op `echo` that still flipped a keyed
  release to a full (trusted-looking) release; it now fails loudly when a key is
  set (signing is unimplemented), and the notes no longer imply `SHA256SUMS.txt`
  authenticates a download.

### Fixed
- **Desktop sidecar no longer orphans on Windows (H3).** The parent-death watcher
  used POSIX-only semantics: `os.kill(pid, 0)` is a harmless probe only on POSIX
  (on Windows it routes through `GenerateConsoleCtrlEvent`/`TerminateProcess` and
  raised an uncaught `OSError`), and orphan reparent-detection never fires there.
  On the shipped Windows target the sidecar leaked on `127.0.0.1` every session.
  The watcher now dispatches by platform — a non-destructive
  `OpenProcess`/`WaitForSingleObject` liveness probe on Windows, the signal-0 probe
  on POSIX — with the reparent heuristic disabled where it is meaningless.

### Changed
- Version bumped to **0.2.0** across core/server (`pyproject.toml`, `__version__`),
  `ui`/`desktop`/`docs-site` `package.json`, `tauri.conf.json`, and `CITATION.cff`;
  the `docs-site` manifest is corrected from a stray `0.0.0`. Contract
  `schema_version` constants are deliberately unchanged.

### Docs
- Added the severity-ranked adversarial review
  ([`docs/handoff/v0.2-review.md`](docs/handoff/v0.2-review.md)) and the release
  handoff ([`docs/handoff/codex-v0.2.md`](docs/handoff/codex-v0.2.md)); corrected
  the stale reviewer dossier `docs/reviews/codex-review-prompt.md` (it still
  described "Phase 0, no engine yet") to the shipped state, and `SECURITY.md`'s
  stale "Phase 0 has no updater" line. Deferred Medium/Low findings are tracked in
  the review's TODO list.

### Added
- **Phase 8 — Exact-score distribution + Casual/Expert presentation.** Goal-based
  families (independent / Dixon-Coles / bivariate Poisson) now seal the
  exact-score distribution the 1X2 forecast already implied, as an additive
  `forecast.score_matrix`: a display grid of concrete scorelines `0..7` per side
  plus an outcome-decomposed `8+` tail bucket. The sealed probabilities, expected
  goals, and grid are all derived from **one** matrix (integrated to 20 goals/
  side), so they are coherent by shared source. A **machine-checked coherence
  invariant** enforces it: `validate_artifact` reproduces win/draw/loss from
  `grid + tail` on every load (rejecting any incoherent matrix), and `seal_forecast`
  additionally proves the matrix mean reproduces `expected_goals` before writing —
  an incoherent matrix aborts the seal rather than being shown. Goal-less families
  (climatological / Elo) and abstained seals carry **no** matrix: an honest
  "no exact-score distribution" state, never a fabricated grid. The schema bumps
  additively within `0.2.0` (existing `0.1.0`/`0.2.0` artifacts still validate);
  sample fixtures regenerated coherently. The AI evidence bundle gains the top-3
  scorelines and the tail as whitelisted `allowed_numbers`, so the AI may cite
  e.g. "most likely 1-1 at 12.6%" — the numeric whitelist still governs, so it
  cannot invent a scoreline or a percentage. A new **Casual ⇄ Expert** toggle
  presents the same sealed numbers at two depths (the toggle never changes
  displayed certainty): Casual = verdict bar + a band-generated plain-language
  summary (not AI) + cited sealed-number facts; Expert = an accessible score-matrix
  heatmap (table semantics, most-likely highlighted, theme-aware, reduced-motion
  safe) with the tail, the model's spread, versions, and calibration context.
- **Phase 7 — Fact & Coincidence engine (the Commentator's Notebook).** A new,
  deterministic `golavo_core.facts` package computes source-backed match facts
  over the vendored CC0 packs. A fixed, pre-registered family of templates
  (`family_size` = 26 hypotheses/match — the multiple-comparison bound) emits
  facts each labelled **predictive / context / coincidence** and carrying its
  sample, denominator, base rate, source ids, and freshness. Guardrails: per-
  template minimum-sample suppression, staleness auto-hide, and a coincidence cap
  (≤3, ranked by specificity not significance) with UI quarantine. Every fact's
  text is number-disciplined, so context/predictive facts fold verbatim into the
  AI evidence bundle's numeric whitelist (coincidences never do). Internationals-
  only scorer/shootout facts; no club scorer/lineup data is fabricated; the
  promoted-team rate is an honest debut-window proxy. A **machine-checked
  no-write invariant** (static import isolation + runtime immutability) proves no
  fact code path can change a probability, forecast, or calibration number.
- Read-only `GET /api/v1/forecasts/{id}/facts` serving a precomputed notebook; a
  `golavo notebook` CLI command; a UI **Commentator's Notebook** panel; and an
  additive `facts.schema.json`. `build_evidence_bundle` gains additive
  `extra_facts`/`extra_numbers` params (default output byte-identical).

## [0.1.0] - 2026-07-11

First tagged release — an **unsigned pre-release**. The source, the deterministic
engine, the optional off-by-default AI layer, and the docs are complete and
tested; the desktop bundles build **unsigned**, so macOS Gatekeeper and Windows
SmartScreen warn on first launch. Code signing, notarization, and the signed
auto-updater are wired but **gated on secrets that are not configured**, so no
signed or notarized artifact is produced or claimed. The calibration record ships
**empty** and only ever accumulates genuine pre-kickoff seals.

### Added
- Phase 6 release hardening. A whole-repo claims/honesty audit
  (`docs/handoff/phase6-claims-audit.md`) reconciled every capability claim with
  shipped, tested code at the release commit. One deterministic end-to-end
  integration test (`server/tests/test_phase6_e2e.py`) composes the whole
  pipeline — provenance-validate packs → ingest → evaluate a fold → forward-seal
  a scheduled fixture on snapshot T0 → score it from T1 → aggregate the
  calibration record → build the evidence bundle → run the AI narration path with
  a **canned adversarial** response and assert the numeric whitelist falls back to
  local-only — with byte-stable artifacts and **no network, no live LLM**.
  Per-competition **model cards** with the real backtest metrics and reliability
  diagrams are generated from the evaluation artifacts by
  `scripts/build_model_cards.py` (never hand-typed). **Authentic screenshots** of
  the running v0.1.0 workbench — matchday, sealed/scored, the calibration record,
  and the AI Deep Read panel OFF and ON — captured over the clearly-labelled
  synthetic sample artifacts and surfaced on the landing page and README. Coherent
  `0.1.0` versioning across `core`/`server`, `ui`, `CITATION.cff`, and the Tauri
  config.
- Phase 5 optional, local-first **AI Deep Read** — off by default and strictly
  additive; the whole app works identically with AI disabled. The deterministic
  engine owns every probability; the AI only explains and cites, and is
  structurally prevented from stating any number the engine did not produce. It
  **does not improve accuracy** and cannot change a probability.
  - `MatchEvidenceBundle` (`golavo_core.evidence`, additive schema
    `evidence_bundle.schema.json` 0.1.0): a pure function of a sealed/scored
    artifact carrying an explicit `allowed_numbers` whitelist — every numeric
    value the AI may utter, each with an id, unit, display string, and citable
    source.
  - AI guards (`golavo_core.ai`, network-free): an exact-display, reference- and
    unit-bound, unicode-safe numeric whitelist matcher; narration review
    that strips chain-of-thought, drops uncited claims, and hard-rejects
    unsupported numbers, betting lexicon, and credential-shaped content;
    an untrusted-text sanitizer; and a fixed, versioned system prompt. Forced
    structured output via `ai_narration.schema.json` 0.1.0.
  - AI gateway (`golavo_server.ai_gateway`), the only module that talks to an
    LLM: OpenAI-compatible (Ollama / llama.cpp) and BYOK OpenAI/Anthropic over
    stdlib `urllib`; injected transport for CI; parse → review → one retry →
    local-only fallback; cache keyed by every prompt-affecting input; keys from
    env/keychain, header-only, never logged.
  - `POST /api/v1/forecasts/{id}/narrative`: additive, off by default; returns a
    guard-validated narration or an explicit off/unavailable/local-only state.
    The read-only forecast surface is unchanged; AI never blocks a forecast.
  - UI "AI Deep Read" panel: off-by-default provider selector, subordinate to the
    sealed numbers, cited claims with source + number chips, factual pipeline
    stages only (never model reasoning), honest fallback states.
  - CI red-team suite (no live LLM): adversarial bundles/responses that try to
    change a probability, fabricate a number/citation, smuggle betting language,
    leak chain-of-thought, or exfiltrate a key — all fail closed to local-only.
  - Post-handoff hardening binds every numeric token to the exact display and id
    referenced by its claim, rejects ambiguous numeric notation, constrains local
    model endpoints to loopback, forbids cloud base-URL overrides, keys caches by
    all prompt-affecting inputs, and invalidates stale UI requests on provider or
    artifact changes.
- Phase 4 desktop app: a Tauri 2 shell that packages the FastAPI core as a
  PyInstaller **onefile sidecar** (`golavo-sidecar-<target-triple>`). On launch it
  picks a free `127.0.0.1` port, mints a per-launch token, spawns the sidecar,
  waits for `/health`, then shows the workbench with `window.__GOLAVO_RUNTIME__`
  injected so the UI talks to the ephemeral port + token (nothing hardcoded); on
  quit it kills the sidecar. A frozen-vs-source resource resolver
  (`golavo_core.resources`) finds the bundled schema/eval summaries under
  `sys._MEIPASS`. The read-only API gains an `x-golavo-token` gate on `/api/*`
  (open in source mode; `/health` + CORS preflight exempt) and Tauri CORS origins.
- Orphan-proof sidecar lifecycle: the sidecar watches the shell pid
  (`--parent-pid`) and self-exits if orphaned — needed because the onefile
  bootloader forks a Python child the shell's kill can't reach directly.
- Packaging + CI: `packaging/build.sh` and `packaging/golavo-sidecar.spec` produce
  unsigned `.dmg` (macOS) and `.msi`/`.exe` (Windows) with `SHA256SUMS`;
  `release.yml` builds them on native runners; `ci.yml` gains a frozen-bundle
  `--smoke` job on macOS + Windows. Signing/notarization and the signed
  auto-updater (pre-update backup + health check + rollback) are wired but
  **gated on secrets** (`TAURI_SIGNING_PRIVATE_KEY`, `APPLE_*`), never fabricated.
- Phase 3 forward sealed-forecast loop (internationals only): seal a genuinely scheduled
  fixture before its conservative day-proxy kickoff (the source has dates, not kickoff
  times), score it from a strictly newer retained snapshot, or void it with a recorded
  reason on postponement/abandonment — the seal's bytes never change.
- Snapshot retention: `build_sourcepack.py` is parameterized by pinned upstream ref,
  output directory, and file set; snapshots are immutable, never re-fetched, and
  registered in the new `packs/snapshots.json`; `validate_provenance.py` discovers every
  pack and cross-checks the registry. A second retained internationals snapshot
  (`273c731492df…`, in which France–Morocco 2026-07-09 is still scheduled) makes the
  seal→score loop replay deterministically in CI against the Phase 0 pack's completed
  result.
- Data-state anchoring: new-pack manifests record `upstream_committed_at_utc` (the pinned
  ref's public commit time) next to the honest `retrieved_at_utc`; seal and score
  validity are checked against the anchor, with retrieval time as the fallback for
  packs built before the anchor existed.
- ForecastArtifact contract 0.2.0 (additive over 0.1.0): optional
  `Snapshot.upstream_committed_at_utc`, optional top-level `void_reason`, shared
  ActualResult/ScoreMetrics defs, and the new CalibrationSummary contract; `golavo void`
  CLI command with a mandatory reason.
- Real calibration record: `golavo_core.calibration` aggregates the immutable ledger's
  sealed→scored/voided chains (one resolution per seal, reconciled counts, running log
  loss/Brier, reliability bins) — never backtests; served read-only at
  `GET /api/v1/calibration` and rendered in the workbench's new Ledger view, clearly
  separated from the evaluation folds.
- Phase 2 club coverage: pinned `openfootball` sourcepacks (CC0-1.0, same upstream ref as
  Phase 1) for La Liga, Bundesliga, Serie A, and Ligue 1 — historical completed seasons
  only, one independently modeled pack per league (no cross-league strength calibration).
  The audit gate is league-aware (expected matches derived from actual team count, checked
  against each league's constitutional size) and excludes, honestly: La Liga & Serie A
  2024-25 (final matchday missing at capture), Ligue 1 2019-20 (COVID abandonment), and
  every league's partial 2025-26 capture.
- Evidence-based team-name canonicalization for es/de/it/fr with a machine-checked proof
  (`scripts/check_team_fragmentation.py`, `docs/handoff/team-canonicalization.md`):
  within-season injectivity, cross-season drift merged, distinct clubs kept distinct.
- Per-league chronological season-fold evaluations (three most recent clean seasons each);
  the combined evaluation API and workbench now surface all five leagues' folds.
- Phase 1 club coverage: pinned `openfootball` English Premier League sourcepack (CC0-1.0)
  gated by a coverage audit (`docs/handoff/openfootball-audit.md`) that accepts 15 clean
  completed seasons (2010-11 → 2024-25) and excludes the partial 2025-26 capture.
- Source-agnostic ingestion (`load_matches` dispatcher) and chronological EPL season-fold
  evaluation reusing the five candidates; `evaluate-club` CLI; combined evaluation API.
- Phase 0 pinned martj42 internationals sourcepack with byte-level provenance validation.
- Deterministic climatological, Elo ordinal-logit, independent Poisson, Dixon-Coles,
  and bivariate-Poisson candidates with chronological WC2022/EURO2024/WC2026 evaluation.
- ForecastArtifact schema 0.1.0, immutable seal/score CLI, sample artifacts, and read-only API routes.
- EvalSummary `fold_id` widened from a fixed enum to a pattern (backward-compatible; admits club folds).
- Initial repository scaffold: README, Apache-2.0 license,
  animated brand marks, contributing/security/conduct policies.
- CI/CD workflows: continuous integration, signed release pipeline (stable + beta),
  and GitHub Pages docs deployment.
- Astro + Starlight documentation site scaffold.
- Package skeletons: `core/` (modeling library), `server/` (FastAPI + `/health`),
  `ui/` (React + Vite), plus `desktop/`, `packaging/`, and `packs/` placeholders.
- ADR-0001: desktop architecture decision (Tauri 2 + FastAPI/Python sidecar).

[Unreleased]: https://github.com/udhawan97/Golavo/compare/v0.2.3...HEAD
[0.2.3]: https://github.com/udhawan97/Golavo/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/udhawan97/Golavo/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/udhawan97/Golavo/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/udhawan97/Golavo/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/udhawan97/Golavo/releases/tag/v0.1.0
