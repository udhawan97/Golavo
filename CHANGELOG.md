# Changelog

All notable changes to Golavo are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
