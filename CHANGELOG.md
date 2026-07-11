# Changelog

All notable changes to Golavo are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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

[Unreleased]: https://github.com/udhawan97/Golavo/commits/main
