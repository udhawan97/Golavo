# Golavo Phase 2 core handoff (top-5 European leagues, historical)

- **Base:** `main` @ `989381a` (developed there; rebased before landing onto `4afed82`,
  which added only dependabot bumps — vite 8, astro 7, GitHub Actions — touching no
  Phase 2 file; UI and docs-site builds were re-verified on the new toolchains).
  Landed on `main` as `9406a79`.
- **Pinned openfootball upstream:** `a5dd38b3bcbe3aa2477cf400f569264253d51431` (committed
  2026-05-30) — the SAME ref as Phase 1; no re-pin, no re-vendoring of the EPL pack.
- **Canonical schema:** `ForecastArtifact` 0.1.0, unchanged. New club fold ids
  (`LALIGA2021-22`, `BUNDESLIGA2022-23`, `SERIEA2021-22`, `LIGUE1-2022-23`, …) already
  match the Phase 1 `fold_id` pattern — no contract change of any kind.
- **Phase 2 scope:** extend lawful HISTORICAL club coverage to the men's top-5 European
  leagues — La Liga (`es.1`), Bundesliga (`de.1`), Serie A (`it.1`), Ligue 1 (`fr.1`) —
  alongside the Phase 1 English Premier League (`en.1`). **Not live.** Each league is
  modeled independently from its own pack; domestic files carry no inter-league matches,
  so there is **NO cross-league strength calibration** and strengths are not comparable
  across leagues.

## Pack structure (decision + why)

One pack per league (`packs/openfootball-esp-ll`, `-deu-bl`, `-ita-sa`, `-fra-l1`),
mirroring `packs/openfootball-eng-pl`: pinned season JSON + CC0-1.0 text + manifest with
per-file SHA-256. Per-league packs were chosen over one multi-league pack because
(1) the league is the modeling unit — packs align 1:1 with independently evaluated
models; (2) the Phase 1 EPL pack is already sealed and referenced by artifacts, and
re-vendoring it would churn provenance for zero gain; (3) `validate_pack` /
`load_matches` / `evaluate_club` work per pack unchanged. Season ranges are the exact
per-league inventory at the pinned ref (listed via the GitHub trees API): es.1 from
2012-13, de.1 from 2010-11, it.1 from 2013-14, fr.1 from 2014-15, all through 2025-26.
`packs/** -text` (EOL exemption) already covers them; bytes survive a clean re-checkout
(verified: `rm -rf` + `git checkout --` + provenance re-run).

## The gate (league-aware audit)

`scripts/audit_openfootball.py` was generalized: with n = the ACTUAL team count in a
season file, a clean season needs exactly n·(n−1) fixtures, every one with a well-formed
two-integer `score.ft`; n−1 home and n−1 away per team; no self-matches, duplicate
ordered pairs, or negative scores; and n must equal the league's constitutional size
(20 for en/es/it; 18 for de; 20 for fr through 2022-23, 18 from 2023-24) — the last
check catches a silently dropped club, which derived-n arithmetic alone cannot see
(n−1 teams at (n−1)·(n−2) matches is self-consistent). Divergent `[0, 0]` LIST scores
and empty `{}` scores are INCOMPLETE, never fabricated. Report:
`docs/handoff/openfootball-audit.{md,json}`.

| League | Verdict | Clean seasons | Excluded, and why |
|---|---|---|---|
| English Premier League | **ACCEPT_HISTORICAL** | 15 (2010-11 → 2024-25) | 2025-26 partial capture (27 `[0, 0]`-encoded placeholders) — unchanged from Phase 1 |
| La Liga | **ACCEPT_HISTORICAL** | 12 (2012-13 → 2023-24) | 2024-25 final matchday absent (10 empty `{}` scores, MD38 2025-05-23/25); 2025-26 partial (15) |
| Bundesliga | **ACCEPT_HISTORICAL** | 15 (2010-11 → 2024-25) | 2025-26 partial capture (12) |
| Serie A | **ACCEPT_HISTORICAL** | 11 (2013-14 → 2023-24) | 2024-25 final matchday absent (10, MD38); 2025-26 partial (36) |
| Ligue 1 | **ACCEPT_HISTORICAL** | 10 (2014-15 → 2024-25) | 2019-20 COVID abandonment (101 of 380 fixtures unplayed from MD28); 2025-26 partial (24) |

Ligue 1's 20→18 contraction in 2023-24 is handled by the audit (380- then 306-match
seasons are both clean). Played matches inside excluded seasons remain training rows —
they really happened; the missing remainder only disqualifies the season as a test fold.
Live in-season updating stays UNVERIFIED until 2026-27; independent second-source
cross-checking stays DEFERRED (footballcsv is stale to ~2020/21, divergent names).

## Team-name canonicalization (evidence first)

`scripts/check_team_fragmentation.py` generated the raw-name inventory per league BEFORE
the canonicalizers were written (openfootball switched to formal legal names in 2020-21;
fr.1 in 2023-24), and now re-proves the shipped mapping on every run:
within-season injectivity everywhere; every adjudicated drift pair merges (incl. the
alias-only ones: `Inter`/`FC Internazionale Milano`, `Lazio Roma`/`SS Lazio`,
`CD Alavés`/`Deportivo Alavés`, `RC Celta`/`RC Celta de Vigo`, `RC Lens`/`Racing Club de
Lens`, `Bor. Mönchengladbach`); adjudicated distinct clubs stay distinct (`Chievo
Verona`≠`Hellas Verona`, `AC Ajaccio`≠`Gazélec Ajaccio`, `Paris FC`≠`Paris
Saint-Germain`); canonical club counts match the evidence (en 41, es 33, de 32, it 38,
fr 34). Judgment call stated openly: `Parma FC` → `Parma Calcio 1913` (2015 bankruptcy /
refoundation) is treated as one sporting identity. The en.1 path is byte-for-byte the
Phase 1 behavior, so EPL match_ids are stable — `eval_summary_epl.json` reproduced
byte-identically after the refactor. Evidence + proof:
`docs/handoff/team-canonicalization.md`.

## Evaluation (log loss primary, lower is better)

Three most recent clean seasons per league (audit-derived): EPL / Bundesliga / Ligue 1
2022-23 → 2024-25; La Liga / Serie A 2021-22 → 2023-24 (their 2024-25 captures are
incomplete). **Every candidate beats the climatological baseline on log loss on every
fold of every league.** The best model varies by fold — Elo ordinal-logit, independent
Poisson, and Dixon-Coles each win somewhere; bivariate Poisson ties independent Poisson
(its tuned dependence stays at zero) — so nothing is crowned. EPL numbers are unchanged
from Phase 1 (`docs/handoff/eval_report_epl.md`).

### La Liga

| Fold | Matches | Model | Log loss | Brier |
|---|--:|---|---:|---:|
| LALIGA2021-22 | 380 | climatological | 1.081100 | 0.654087 |
| LALIGA2021-22 | 380 | elo_ordlogit | 1.005811 | 0.601319 |
| LALIGA2021-22 | 380 | poisson_independent | 1.008891 | 0.601732 |
| LALIGA2021-22 | 380 | dixon_coles | 1.004469 | 0.599438 |
| LALIGA2021-22 | 380 | bivariate_poisson | 1.008891 | 0.601732 |
| LALIGA2022-23 | 380 | climatological | 1.051916 | 0.634221 |
| LALIGA2022-23 | 380 | elo_ordlogit | 1.000621 | 0.596800 |
| LALIGA2022-23 | 380 | poisson_independent | 0.986303 | 0.587275 |
| LALIGA2022-23 | 380 | dixon_coles | 0.993632 | 0.592335 |
| LALIGA2022-23 | 380 | bivariate_poisson | 0.986303 | 0.587275 |
| LALIGA2023-24 | 380 | climatological | 1.076666 | 0.651199 |
| LALIGA2023-24 | 380 | elo_ordlogit | 1.003028 | 0.598633 |
| LALIGA2023-24 | 380 | poisson_independent | 0.974283 | 0.579454 |
| LALIGA2023-24 | 380 | dixon_coles | 0.969400 | 0.576471 |
| LALIGA2023-24 | 380 | bivariate_poisson | 0.974283 | 0.579454 |

### Bundesliga

| Fold | Matches | Model | Log loss | Brier |
|---|--:|---|---:|---:|
| BUNDESLIGA2022-23 | 306 | climatological | 1.056926 | 0.637581 |
| BUNDESLIGA2022-23 | 306 | elo_ordlogit | 0.994742 | 0.593951 |
| BUNDESLIGA2022-23 | 306 | poisson_independent | 0.993077 | 0.592215 |
| BUNDESLIGA2022-23 | 306 | dixon_coles | 0.996967 | 0.595057 |
| BUNDESLIGA2022-23 | 306 | bivariate_poisson | 0.993077 | 0.592215 |
| BUNDESLIGA2023-24 | 306 | climatological | 1.075414 | 0.650504 |
| BUNDESLIGA2023-24 | 306 | elo_ordlogit | 1.026377 | 0.614837 |
| BUNDESLIGA2023-24 | 306 | poisson_independent | 1.019684 | 0.609168 |
| BUNDESLIGA2023-24 | 306 | dixon_coles | 1.028728 | 0.615926 |
| BUNDESLIGA2023-24 | 306 | bivariate_poisson | 1.019684 | 0.609168 |
| BUNDESLIGA2024-25 | 306 | climatological | 1.093035 | 0.664265 |
| BUNDESLIGA2024-25 | 306 | elo_ordlogit | 1.023666 | 0.613969 |
| BUNDESLIGA2024-25 | 306 | poisson_independent | 1.035313 | 0.621655 |
| BUNDESLIGA2024-25 | 306 | dixon_coles | 1.033770 | 0.620569 |
| BUNDESLIGA2024-25 | 306 | bivariate_poisson | 1.035313 | 0.621655 |

### Serie A

| Fold | Matches | Model | Log loss | Brier |
|---|--:|---|---:|---:|
| SERIEA2021-22 | 380 | climatological | 1.090016 | 0.661707 |
| SERIEA2021-22 | 380 | elo_ordlogit | 1.005193 | 0.600153 |
| SERIEA2021-22 | 380 | poisson_independent | 1.006514 | 0.600835 |
| SERIEA2021-22 | 380 | dixon_coles | 1.004468 | 0.599787 |
| SERIEA2021-22 | 380 | bivariate_poisson | 1.006514 | 0.600835 |
| SERIEA2022-23 | 380 | climatological | 1.079223 | 0.653455 |
| SERIEA2022-23 | 380 | elo_ordlogit | 1.004013 | 0.599253 |
| SERIEA2022-23 | 380 | poisson_independent | 1.011995 | 0.604271 |
| SERIEA2022-23 | 380 | dixon_coles | 1.009123 | 0.602704 |
| SERIEA2022-23 | 380 | bivariate_poisson | 1.011995 | 0.604271 |
| SERIEA2023-24 | 380 | climatological | 1.087997 | 0.658701 |
| SERIEA2023-24 | 380 | elo_ordlogit | 1.018245 | 0.610878 |
| SERIEA2023-24 | 380 | poisson_independent | 1.002934 | 0.600315 |
| SERIEA2023-24 | 380 | dixon_coles | 0.998515 | 0.598882 |
| SERIEA2023-24 | 380 | bivariate_poisson | 1.002934 | 0.600315 |

### Ligue 1

| Fold | Matches | Model | Log loss | Brier |
|---|--:|---|---:|---:|
| LIGUE1-2022-23 | 380 | climatological | 1.074716 | 0.650714 |
| LIGUE1-2022-23 | 380 | elo_ordlogit | 1.018985 | 0.608656 |
| LIGUE1-2022-23 | 380 | poisson_independent | 1.021633 | 0.609349 |
| LIGUE1-2022-23 | 380 | dixon_coles | 1.022936 | 0.609534 |
| LIGUE1-2022-23 | 380 | bivariate_poisson | 1.021633 | 0.609349 |
| LIGUE1-2023-24 | 306 | climatological | 1.091744 | 0.662660 |
| LIGUE1-2023-24 | 306 | elo_ordlogit | 1.044521 | 0.628899 |
| LIGUE1-2023-24 | 306 | poisson_independent | 1.033691 | 0.620336 |
| LIGUE1-2023-24 | 306 | dixon_coles | 1.034938 | 0.621973 |
| LIGUE1-2023-24 | 306 | bivariate_poisson | 1.033691 | 0.620336 |
| LIGUE1-2024-25 | 306 | climatological | 1.053458 | 0.636318 |
| LIGUE1-2024-25 | 306 | elo_ordlogit | 0.995975 | 0.593816 |
| LIGUE1-2024-25 | 306 | poisson_independent | 0.979446 | 0.582022 |
| LIGUE1-2024-25 | 306 | dixon_coles | 0.984414 | 0.585297 |
| LIGUE1-2024-25 | 306 | bivariate_poisson | 0.979446 | 0.582022 |

## What shipped

- `scripts/build_openfootball_pack.py`: league registry + per-league pack builder at the
  pinned ref (default: the four Phase 2 leagues; en.1 is never re-vendored).
- Four new vendored packs with per-file SHA-256 manifests + CC0 text;
  `scripts/validate_provenance.py` covers all six packs.
- `scripts/audit_openfootball.py`: league-aware gate (per-league verdicts, named
  exclusions) → `docs/handoff/openfootball-audit.{md,json}`.
- `scripts/check_team_fragmentation.py` + `docs/handoff/team-canonicalization.md`:
  fragmentation evidence and the machine-checked canonicalization proof.
- `golavo_core.ingest.openfootball`: `LEAGUES` registry; file-name-driven league
  detection; per-league `canonical_team(name, league)`; per-row competition in match
  identities (en.1 identities unchanged).
- `golavo_core.evaluation`: `CLUB_FOLDS_BY_COMPETITION` (audit-mirrored folds),
  `evaluate_club` dispatches on the pack's manifest competition; per-league honest
  report notes; `evaluate-club` CLI unchanged in interface.
- Per-league artifacts: `eval_summary_{laliga,bundesliga,seriea,ligue1}.json` +
  `eval_report_*.md` (EPL files regenerated, summary byte-identical).
- Server: `/api/v1/eval/summary` merges all six summaries (internationals + five
  leagues) in declared order; new merge test.
- UI: bundled mock refreshed to the exact server-merged shape (18 folds, 7 competition
  groups); the workbench evaluation view renders all leagues with zero console errors
  (verified via dev server: grouping, fold selector, reliability diagram for
  `LIGUE1-2024-25`).
- Tests: `core/tests/test_phase2.py` (canonicalization merges/distinctions, loader
  counts/tagging, per-league audit verdicts, fold-registry↔audit consistency, La Liga
  full-eval gate + schema, committed-summary honesty checks) + updated Phase 1 audit
  test; 24 passed.
- Docs: README coverage matrix per league, docs-site coverage page with the verdict
  table, packs/README vendored-sourcepack table, CHANGELOG.

## Known gaps (honest)

- **No cross-league strength calibration** — domestic files have no inter-league
  matches; strengths are league-internal by construction. Do not compare them.
- **No live coverage, no club seals.** openfootball is historical here; a seal requires
  `as_of` after retrieval and before kickoff, which no already-played match satisfies.
  Live cadence remains unverified until a season is observed updating (2026-27).
- La Liga & Serie A stop at 2023-24 for folds: their 2024-25 captures miss the final
  matchday at this pin. A clean re-pin would likely promote them; not fabricated now.
- Ligue 1 sits exactly at the 10-clean-season gate minimum — the thinnest accepted
  league; its training history is also the shortest (2014-15 on).
- openfootball kickoff times are venue-local and used as-is (historical packs).
- Lineups, injuries, corners, shots, cards, and xG still have **no accepted open
  source**. Second-source cross-checking of results remains deferred.
- The audit's constitutional league sizes (20/20/20/18; fr 20→18 at 2023-24) are encoded
  facts about the competitions, not derived from the files — by design, to catch
  dropped-club corruption.

## Reproduce

```bash
python scripts/build_openfootball_pack.py            # network build step (four packs)
python scripts/validate_provenance.py                # byte-exactness, all six packs
python scripts/audit_openfootball.py                 # per-league gate verdicts
python scripts/check_team_fragmentation.py           # canonicalization proof
python -m golavo_core evaluate-club --pack packs/openfootball-esp-ll \
  --summary docs/handoff/eval_summary_laliga.json --report docs/handoff/eval_report_laliga.md
pytest -q && ruff check . && (cd ui && npm run build)
```
