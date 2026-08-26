# Golavo public-surface fact sheet

Verified against the product source in the same commit as this file and the public
v0.18.0 release on 2026-08-25. The refresh started from
`a2aa0277ab9ac96fe3efa99deb525e5152879cef`; use the containing Git commit as the
authority for later reads. This ledger exists to keep the README,
documentation site, download paths, and release notes from collapsing source behavior,
packaged-release behavior, and future work into one claim.

## Distribution state

| Claim | Status | Evidence | Public wording |
|---|---|---|---|
| Latest packaged release | v0.18.0, tag commit `9ed4218d8ae84266bd5e7d99b2a44886143b1393` | GitHub release assets include Apple Silicon DMG/app updater payload, Windows x64 EXE/MSI, `latest.json`, aggregate checksums, and detached signatures | Call v0.18.0 the newest packaged desktop release; keep the OS-unsigned warning |
| Repository source | The containing `main` commit is ahead of v0.18.0 | Git history plus the current source, tests, and contract files | Label the newer tools as source behavior until a later release contains them |
| Public website | GitHub Pages from `docs-site/` on `main` | `.github/workflows/pages.yml`, `docs-site/astro.config.mjs` | The site may document source behavior, but every download surface must retain the release boundary |

## Current product claims

| Capability | Source evidence | Boundary that must travel with the claim |
|---|---|---|
| Deterministic match forecasts | `core/golavo_core/`, `server/golavo_server/main.py` | The statistical engine owns every probability; model voices are not averaged |
| Sealed and scored forecast artifacts | `core/golavo_core/artifacts.py`, `docs/contracts/forecast_artifact.schema.json` | A scored/voided successor never rewrites the seal; bytes and local checkpoints do not prove timing, while independent pre-cutoff publication can add external timing evidence |
| Portable forecast proof | `core/golavo_core/proof.py` | Included bytes and lineage can verify locally; descriptor-only source bytes, authenticity, completeness, creation time, and accuracy are not proved |
| Local checkpoint chain | `server/golavo_server/ledger_checkpoints.py` | Detects changes relative to earlier local checkpoints; no external authenticity or real-world timestamp proof; migration/recovery/anchoring remain gated |
| Forecast-ledger archive/restore | `server/golavo_server/personal_archive.py` | Includes forecast artifacts, picks, and followed-match state only; excludes team favorites, credentials, providers, overlays, weather, research, refresh generations, checkpoints, and caches |
| Data-application receipts | `server/golavo_server/refresh_receipts.py`, `server/golavo_server/refresh_jobs.py` | Local append-only application history, not a tamper-proof external audit; stable-identity comparisons never guess unresolved rekeys |
| My Teams | `ui/src/views/MyTeams.tsx`, `ui/src/lib/favorite-teams.ts` | Local browser preference keyed by exact competition/team identity; one named outlook voice; descriptive simulation, not advice or a seal |
| Follow calendar | `server/golavo_server/calendar_export.py` | RFC 5545 static export; only exact UTC kickoffs; date-only or unknown times are omitted |
| Guarded calibration slices | `core/golavo_core/calibration.py`, `ui/src/views/PredictionLedger.tsx` | Metrics begin at 30 scored seals; reliability needs 100 scored seals and three bins of at least 20; descriptive local cuts, not comparisons |
| Optional providers and AI | `server/golavo_server/ai_gateway.py`, `server/golavo_server/sportmonks.py`, `ui/src/views/Settings.tsx` | Separate consent; AI cannot author a number; Sportmonks stays an attributed outside signal and never enters a Golavo forecast |

## Installation paths

| Path | Requirements | Availability |
|---|---|---|
| macOS desktop | Apple Silicon, unsigned DMG | v0.18.0 release |
| Windows desktop | x64 Windows 10/11, unsigned EXE or MSI | v0.18.0 release |
| Browser/source mode | Python 3.12+, Node 22+, source checkout | Current `main` read paths and My Teams; archive restore and checkpoint creation require a desktop source build with its private launch token |

## Explicit non-claims

- No account, telemetry, hosted forecasting backend, bet placement, affiliate path, or
  bookmaker workflow.
- No confirmed-lineup, injury, observed-xG, or leakage-safe historical-weather model inputs.
- No second independent club-result source; automatic club settlement stays pending.
- No OS-signed/notarized desktop installers.
- No claim that a local checkpoint proves external authenticity, creation time, or
  disaster recovery across versions.
- No claim that the v0.18.0 installers contain post-release source features.

## Refresh checklist

Before changing a public claim, compare the current code, `CHANGELOG.md`, the latest
GitHub release/tag/assets, and the rendered site. Re-run the docs check/build and link scan;
for release work, repeat artifact/signature/installed-app verification instead of reusing
this snapshot.
