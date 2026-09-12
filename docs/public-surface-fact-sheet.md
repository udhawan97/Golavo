# Golavo public-surface fact sheet

Prepared against the published v0.20.0 release at
`0b188f6d9fc973f8f97d3347aafa0c75300fb866` and the product source. The hosted
artifacts, signatures, updater metadata, mounted macOS app, and frozen sidecar were verified
after publication; Windows artifacts were authenticated and structurally validated but were
not executed on macOS. This ledger exists to keep the README,
documentation site, download paths, and release notes from collapsing source behavior,
packaged-release behavior, and future work into one claim.

## Distribution state

| Claim | Status | Evidence | Public wording |
|---|---|---|---|
| Published stable release | v0.20.0; tag commit `0b188f6d9fc973f8f97d3347aafa0c75300fb866` | Stable GitHub release verified with Apple Silicon DMG/app updater payload, Windows x64 EXE/MSI, `latest.json`, aggregate checksums, detached signatures, SBOMs, and release inventories | Retain the OS-unsigned warning; Windows packages were not executed during the macOS verification pass |
| Repository source | The containing documentation commit; packaged authority remains the exact v0.20.0 tag | Git history plus the current source, tests, and contract files | Distinguish current source documentation from the tagged packaged release |
| Public website | GitHub Pages from `docs-site/` on `main` | `.github/workflows/pages.yml`, `docs-site/astro.config.mjs` | The site may document source behavior, but every download surface must retain the release boundary |

## Current product claims

| Capability | Source evidence | Boundary that must travel with the claim |
|---|---|---|
| Deterministic match forecasts | `core/golavo_core/`, `server/golavo_server/main.py` | The statistical engine owns every probability; model voices are not averaged |
| Sealed and scored forecast artifacts | `core/golavo_core/artifacts.py`, `docs/contracts/forecast_artifact.schema.json` | A scored/voided successor never rewrites the seal; bytes and local checkpoints do not prove timing, while independent pre-cutoff publication can add external timing evidence |
| Portable forecast proof | `core/golavo_core/proof.py` | Included bytes and lineage can verify locally; descriptor-only source bytes, authenticity, completeness, creation time, and accuracy are not proved |
| Local checkpoint chain | `server/golavo_server/ledger_checkpoints.py` | Detects changes relative to earlier local checkpoints; format `0.2.0` can extend a verified `0.1.0` head without rewriting old bytes; no external authenticity or real-world timestamp proof |
| Forecast-ledger archive/restore | `server/golavo_server/personal_archive.py` | Includes forecast artifacts, picks, followed-match state, and the verified head-reachable checkpoint chain when present; accepts legacy archives and rehearses recovery in a disposable ledger before mutation; excludes team favorites, credentials, providers, overlays, weather, research, refresh generations, and caches |
| Data-application receipts | `server/golavo_server/refresh_receipts.py`, `server/golavo_server/refresh_jobs.py` | Local append-only application history, not a tamper-proof external audit; stable-identity comparisons never guess unresolved rekeys |
| My Teams | `ui/src/views/MyTeams.tsx`, `ui/src/lib/favorite-teams.ts` | Local browser preference keyed by exact competition/team identity; one named outlook voice; descriptive simulation, not advice or a seal |
| Team dossier | `ui/src/views/TeamDossier.tsx`, `ui/src/lib/team-route.ts` | Exact competition/team identity; observed record, complete separate model voices, and competition-scoped context remain distinct; incomplete voice identity withholds the comparison |
| Selected-match player dossier | `ui/src/components/OutsideSignals.tsx`, `ui/src/lib/sportmonks.ts` | Opens only from an already-fetched exact provider fixture/player identity; no new request or persistence; one fixture is not a career profile, form series, ranking, model input, AI evidence, or export |
| Follow calendar | `server/golavo_server/calendar_export.py` | RFC 5545 static export; only exact UTC kickoffs; date-only or unknown times are omitted |
| Guarded calibration slices | `core/golavo_core/calibration.py`, `ui/src/views/PredictionLedger.tsx` | Metrics begin at 30 scored seals; reliability needs 100 scored seals and three bins of at least 20; descriptive local cuts, not comparisons |
| Match Study Desk | `ui/src/components/MatchStudyDesk.tsx`, `ui/src/lib/markets.ts` | Fixed, unranked engine-owned lenses; mathematical `1/p` equivalence is not a recommendation; missing card/corner/scorer models remain unavailable |
| Optional providers and AI | `server/golavo_server/ai_gateway.py`, `server/golavo_server/sportmonks.py`, `ui/src/views/Settings.tsx` | Separate consent; AI cannot author or verify a number; Sportmonks stays attributed no-store context and never enters a Golavo forecast |
| Transfer Desk | `server/golavo_server/sportmonks.py`, `ui/src/views/Transfers.tsx` | Exact top-five club identity, four-page/365-day bounds, visible partial coverage, free-text provider amount and no invented payment components; fixture-tested until a credentialed smoke succeeds |
| Product captures | `docs-site/public/screenshots/match-study-desk.png`, `docs-site/public/screenshots/transfer-desk.png`, `docs-site/public/screenshots/my-teams-source-main.png` | Captured from local engine flows; the Transfer Desk image intentionally shows the no-fetch installed-app boundary rather than fabricated provider rows |

## Installation paths

| Path | Requirements | Availability |
|---|---|---|
| macOS desktop | Apple Silicon, unsigned DMG | v0.20.0 published; checksum, updater signature, deep ad-hoc bundle signature, embedded SHA, and frozen-sidecar smoke verified |
| Windows desktop | x64 Windows 10/11, unsigned EXE or MSI | v0.20.0 published; checksums, updater signatures, manifest, SBOM, and inventory verified; installers not executed on macOS |
| Browser/source mode | Python 3.12+, Node 22+, source checkout | Read paths; archive restore, checkpoints, and OS-keychain provider setup require a desktop build with its private launch token |

## Explicit non-claims

- No account, telemetry, hosted forecasting backend, bet placement, affiliate path, or
  bookmaker workflow.
- No card, corner, scorer, confirmed-lineup, injury, observed-xG, multi-match player-form,
  transfer, or leakage-safe historical-weather model inputs.
- No second independent club-result source; automatic club settlement stays pending.
- No OS-signed/notarized desktop installers.
- No claim that a local checkpoint proves external authenticity or creation time. The
  recovery drill proves only that the archived local bytes rebuild a valid local chain.
- No claim that later releases are published until their exact tag, assets, signatures, and public surfaces pass the release gate.

## Refresh checklist

Before changing a public claim, compare the current code, `CHANGELOG.md`, the latest
GitHub release/tag/assets, and the rendered site. Re-run the docs check/build and link scan;
for release work, repeat artifact/signature/installed-app verification instead of reusing
this snapshot.
