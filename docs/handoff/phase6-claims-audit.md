# Phase 6 — whole-repo claims & honesty audit

**Base commit:** `efe17ce` (`docs(phase5): mark AI contract IMPLEMENTED + Codex handoff`).
**Branch:** `lane/phase6`. **Date:** 2026-07-11.

Every capability claim across `README.md`, `CHANGELOG.md`, `NOTICE`, `docs/**`,
and `docs-site/src/content/docs/**` was enumerated and checked against the code
**and tests** that exist at this commit. Metric claims were recomputed from the
committed `docs/handoff/eval_summary*.json` artifacts; coverage claims were
cross-checked against `docs/handoff/openfootball-audit.json`.

**Result:** zero unsupported claims remain. The substantive engine, forward-loop,
calibration, and AI claims were already **true and test-backed**; the drift was a
band of `docs-site` + `README` pages that were written around Phase 3 and never
caught up to Phases 4 (desktop) and 5 (AI) shipping — they *understated* the app
(calling shipped AI/desktop "planned") and, in a few places, made now-false "no
AI / no updater / one data source" statements. Those were fixed. A single genuine
*overstatement* — "unsigned build **works**" — was softened to match what is
actually CI-proven.

Verdict legend: **TRUE** = claim verified against shipped + tested code at this
SHA; **FIXED** = claim was drifted/inaccurate and was corrected; **REMOVED** =
claim was deleted or downgraded because it could not be made true.

---

## 1. Verified TRUE (shipped + tested; no change needed)

| Claim | Evidence at this SHA |
|---|---|
| Deterministic engine owns every probability; five candidates evaluated chronologically | `core/golavo_core/models/candidates.py`, `core/golavo_core/evaluation.py`; `core/tests/test_phase0.py` |
| **"Every candidate beats the climatological baseline on log loss on every fold"** (README:135, coverage.md, model-cards) | Recomputed from all six `eval_summary*.json`: TRUE for all 18 international + club folds (see §5) |
| Forward seal→score loop: seal before a conservative day-proxy (00:00 UTC) kickoff; score from a strictly-newer snapshot; seal bytes never change | `core/golavo_core/artifacts.py:175-330`; `core/tests/test_phase3.py::test_forward_loop_replays_deterministically`, `::test_seal_rejects_as_of_at_or_after_day_proxy_kickoff` |
| Void with a **mandatory** reason; voided/scored are terminal | `artifacts.py:333-354`; `test_phase3.py::test_void_supersedes_with_reason_and_without_a_result` |
| Two retained internationals snapshots; `packs/snapshots.json` registry cross-checked in CI (7 snapshots) | `scripts/validate_provenance.py`; ran clean (`registry: OK (7 retained snapshots)`) |
| Calibration record aggregates the immutable ledger (one resolution per seal, running log loss/Brier, reliability bins) and is **never** a backtest | `core/golavo_core/calibration.py`; `test_phase3.py::test_calibration_summary_aggregates_real_chains` |
| **"The calibration record starts small and honest / only genuine pre-kickoff seals"** (README:131) | `data/artifacts/` ships absent → empty zero-count record; `server/golavo_server/runtime.py:44,49`; `server/tests/test_api.py::test_calibration_route_is_honest_about_an_empty_ledger` |
| ForecastArtifact contract **0.2.0** (additive over 0.1.0) | `docs/contracts/forecast_artifact.schema.json` `$id …0.2.0`; `artifacts.py:26` |
| AI layer implemented, **off by default**, cannot change/improve a number; numeric whitelist rejects the whole narration on any unlisted number and falls back local-only | `core/golavo_core/ai/`, `core/golavo_core/evidence.py`, `server/golavo_server/ai_gateway.py`; 76 AI tests incl. `test_phase5_redteam.py` (16 attacks) + `test_ai_gateway.py::test_adversarial_response_falls_back_to_local_only` (6 attacks) — **no live LLM** |
| Gateway is the only LLM-talking module; keys header-only, never logged; injected transport for CI | `ai_gateway.py:1,148-223,298-383`; `test_ai_gateway.py::test_api_key_only_ever_lives_in_the_request_header` |
| Desktop: Tauri 2 shell + PyInstaller sidecar; loopback port + per-launch `x-golavo-token` gate on `/api/*`; frozen resource resolver | `desktop/src-tauri/src/lib.rs`, `server/golavo_server/main.py:28-56`, `core/golavo_core/resources.py`; `server/tests/test_sidecar.py` (token gate + `_MEIPASS` resolver **tested**); CI `sidecar-smoke` freezes + boots on macOS **and** Windows |
| Signing / notarization / signed auto-updater are **wired but gated on secrets, never fabricated**; `check_for_update` returns `disabled` by default | `.github/workflows/release.yml:82-92`, `desktop/src-tauri/src/updater.rs:99-112`, `tauri.conf.json:30` (`createUpdaterArtifacts:false`) |
| Data honesty: only CC0 martj42 + openfootball packs vendored; Transfermarkt/DataHub etc. rejected | `NOTICE`, `packs/*/manifest.json`, provenance CI |

---

## 2. FIXED — drift corrected (understatement / now-false statements)

The recurring root cause: "Phase 0" framing that predated Phases 4–5.

| File:line (post-fix) | Was | Verdict → Fix |
|---|---|---|
| `README.md:25` (status) | "pre-alpha (Phase 3 …). No installable build yet. Desktop, AI narration, and BYOK remain planned." | FIXED → "v0.1.0 — unsigned pre-alpha"; lists shipped AI (off by default) + unsigned desktop; only signing/adapters/cups remain planned/gated |
| `README.md:87` (run modes) | "Source web app … planned (ADR-0001, Phase 2)" | FIXED → source web app is working (`make dev`) |
| `README.md` privacy §147 | "Phase 0 has no account, telemetry, ads, BYOK keys, AI calls, or updater." | FIXED → no runtime network **unless opted in**; AI off by default; BYOK keys stay in keychain/env, never logged; updater gated |
| `README.md` roadmap | Phase 4 deliverable "notarized DMG + signed EXE" with no status | FIXED → status column; Phase 4 = "unsigned build (macOS verified locally); signing gated"; Phase 5 shipped |
| `docs-site/index.mdx` | "no account, telemetry, ads, keys, AI, or updater"; "AI layer is planned"; "Phase 0 … one internationals sourcepack … Club data out of scope"; "no installable build yet" | FIXED → AI shipped off by default; club leagues (historical) in scope; v0.1.0 unsigned pre-release caution |
| `docs-site/introduction.md:6,12,37,19` | AI layer, desktop app, calibration ledger all "planned"; "AI \| Planned, out of Phase 0" | FIXED → AI implemented (Phase 5, off by default); desktop + calibration shipped; only hash-chained ledger/fact engine planned |
| `docs-site/architecture.md:9` | "…**an AI gateway**, and a hash-chained ledger remain planned" | FIXED → AI gateway shipped in Phase 5 (off by default); DuckDB/SQLite/hash-chained ledger still planned |
| `docs-site/data/sources.md:6,18` | "Phase 0 accepts **one** data source"; "OpenFootball … not a Phase 0 dependency" | FIXED → two CC0 upstreams vendored; openfootball is adopted (historical), passed its per-league audit |
| `docs-site/data/coverage.md:3,6,14` | "implemented by Phase 0"; "internationals **only**"; "## Phase 0 coverage" over a club table | FIXED → reframed as the historical starting point; heading retitled; club leagues shown as current coverage |
| `docs-site/privacy-security.md:6,23` | "has no … AI, provider keys, desktop sidecar, or updater"; sidecar/keys/injection "not Phase 0 capabilities" | FIXED → optional off-by-default AI; sidecar token gate; keys keychain-only; signed packs/updates gated |
| `docs-site/matchday.md:18` | "AI Deep Read … (**Phase 6**)" | FIXED → AI Deep Read is **Phase 5, shipped, off by default** |
| `docs-site/build-from-source.md:35` | "`make` targets are **placeholders** during Phase 0–1" | FIXED → make targets are live |
| `docs-site/roadmap.md:16` | Phase 4 "signed updater, notarized DMG + signed EXE" (no status) | FIXED → "✅ shipped, unsigned"; signing wired but gated |
| `docs-site/installation.md:35`, `build-from-source.md:8` | Inconsistent Python floor ("3.12" vs "3.11+"); `requires-python` was `>=3.11` | FIXED → **Python 3.12+** everywhere, and `requires-python` bumped to `>=3.12`. The pinned `scipy==1.18.0` requires 3.12 (surfaced by the first desktop build, which used Python 3.11 and failed); the project genuinely needs 3.12. |

---

## 3. REMOVED / downgraded (overstatement, or capability without a source)

| File:line | Was | Verdict → Action |
|---|---|---|
| `README.md:87` + status | "unsigned build **works**" | REMOVED (overstatement) → "unsigned build — macOS verified locally, macOS + Windows built by the release CI." Rationale: the full Tauri bundle is **not built in CI** (only on tag); "works" was a local manual macOS verification per `codex-phase4.md`, never CI-proven, Windows never built locally. |
| `docs-site/matchday.md:16`, `local-intelligence.md:10` | "likely scorers and expected corners" / "(where data allows) scorers and corners" | REMOVED → marked planned. No accepted open source supplies scorers/corners and no model exists (`models/` has only `candidates.py`). |
| `docs-site/matchday.md:22-24` | "Team, player & manager dossiers … from CC0 data and Wikidata … with original artwork" as a current screen | DOWNGRADED → "*(planned)*"; Wikidata is not a current dependency; dossiers not built. |
| `docs-site/introduction.md:19` | "proprietary feeds are bring-your-own-key and never re-shared" (implies shipped BYOK feed adapters) | DOWNGRADED → BYOK *AI provider* keys ship; BYOK *data-feed* adapters are planned. |

---

## 4. Release/signing honesty

- The release workflow already emits a top-level `SHA256SUMS.txt` over all
  published files (`release.yml` publish job) and `packaging/build.sh` emits a
  per-bundle `SHA256SUMS`. **No SBOM is wired** anywhere (only an SPDX license-id
  check in `scripts/build_openfootball_pack.py`) — so none is claimed.
- `release.yml` was updated so an **unsigned** build publishes as a GitHub
  **pre-release** (no `MINISIGN_SECRET_KEY`) with an explicit unsigned-pre-release
  body. No signed/notarized artifact is produced or claimed; the user holds none
  of the signing secrets (`TAURI_SIGNING_PRIVATE_KEY`, `APPLE_*`, `MINISIGN_*`).
- The Tauri updater public key in `tauri.updater.conf.json` is still the
  placeholder `REPLACE_WITH_TAURI_UPDATER_PUBLIC_KEY`, so even a
  `--features updater` build is non-functional until a real key is supplied. This
  is consistent with "updater disabled by default" and is documented, not hidden.

---

## 5. Coverage & metrics — recomputed from artifacts (not hand-typed)

Per-league clean-season counts match `docs/handoff/openfootball-audit.json`
exactly:

| League (code) | Clean seasons | Excluded (audit reason) |
|---|---:|---|
| English Premier League (en.1) | 15 (2010-11→2024-25) | 2025-26 (27/380 missing) |
| La Liga (es.1) | 12 (2012-13→2023-24) | 2024-25 (10 missing), 2025-26 |
| Bundesliga (de.1) | 15 (2010-11→2024-25) | 2025-26 |
| Serie A (it.1) | 11 (2013-14→2023-24) | 2024-25 (10 missing), 2025-26 |
| Ligue 1 (fr.1) | 10 (2014-15→2024-25) | 2019-20 (COVID, 101 missing), 2025-26 |

"Every candidate beats the climatological baseline on log loss on every fold" —
recomputed across all six competitions (3 folds each = 18 folds): **TRUE** in
every case. The public model cards
(`docs-site/src/content/docs/methodology/model-cards.md`) are regenerated from
these same artifacts by `scripts/build_model_cards.py`.

---

## 6. Remaining honest gaps (documented, not shipped)

- **Desktop full-bundle build is not CI-proven** until the `v0.1.0` tag build
  runs; the shell launch + orphan watchdog are code-only (manual macOS
  verification per `codex-phase4.md`). No end-to-end desktop test exists.
- **No signed/notarized artifacts** — gated on secrets the user does not have.
- **Not built / out of scope:** club lineups / injuries / xG / corners,
  goalscorer modeling, women's football, live club data, confirmed-lineup
  forecasts, BYOK data-feed adapters, a hash-chained ledger (append-only JSONL
  only), women's/cup competitions.
- **Calibration record is empty** by design (0 genuine seals) until a real
  upstream refresh seals a live fixture.
- The README and the docs-site roadmap use different phase *numbering* (delivery
  vs. aspirational MVP plan) — a pre-existing convention; neither overstates after
  this pass.
