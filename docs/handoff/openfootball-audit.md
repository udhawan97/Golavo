# openfootball English Premier League — coverage audit (Phase 1 gate)

- **Pack:** `packs/openfootball-eng-pl`
- **Upstream ref:** `a5dd38b3bcbe3aa2477cf400f569264253d51431` (committed 2026-05-30)
- **Seasons vendored:** 16 (2010-11 → 2025-26)
- **Clean seasons:** 15 (2010-11 → 2024-25)
- **Flagged seasons:** 2025-26
- **Verdict:** **ACCEPT_HISTORICAL**

## Criteria

| Criterion | Result | Basis |
|---|---|---|
| Usable clean seasons (≥10) | PASS | 15 seasons are 380/380 complete with valid double-round-robin structure |
| Structural consistency (all seasons) | PASS | no self-matches, no negative scores, no duplicate ordered pairs in any season |
| Latest clean season present | PASS | 2024-25 is fully clean |
| Freshness (historical-current) | PASS | latest clean season is the immediately prior completed season |

## The 2025-26 anomaly (why it is excluded)

openfootball 2025-26 carries **27 matches whose `score` is a divergent `[0, 0]` list**
rather than the usual `{"ft": [h, a]}` object. That encoding appears in **no other**
of the 16 seasons, and every one of the 27 is uniformly `[0, 0]` — the signature of
results not yet finalized at the 2026-05-30 capture, not 27 genuine goalless draws.
Golavo treats them as **INCOMPLETE** (it does not fabricate them as 0-0), so 2025-26 is
a **partial capture (353/380)** and is excluded from the clean set until a clean re-pin.
This mirrors the Phase 0 treatment of the partial WC2026 fold.

**Live in-season updating:** UNVERIFIED until the 2026-27 season starts — sealing *upcoming* club
fixtures cannot be certified until openfootball is observed updating during a live season.

**Independent cross-source correctness:** DEFERRED (footballcsv stale to ~2020/21; divergent team names). Correctness
here rests on double-round-robin structural integrity, which catches transcription
corruption but is not a substitute for a second independent transcription.

## Scope decision

Club coverage is **ACCEPTED for completed-season, historical use** on the 15
clean seasons (2010-11 → 2024-25). Golavo may build and backtest a Premier
League model on these and ship it labelled **historical / not live**. It must **not**
claim live in-season club forecasting until openfootball is verified updating during a
live season, and it excludes the partial 2025-26 capture.

## Per-season summary

| Season | Matches | Complete | Anomalous | Teams | Home/team | Away/team | Clean |
|---|--:|--:|--:|--:|:--:|:--:|:--:|
| 2010-11 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2011-12 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2012-13 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2013-14 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2014-15 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2015-16 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2016-17 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2017-18 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2018-19 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2019-20 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2020-21 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2021-22 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2022-23 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2023-24 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2024-25 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2025-26 | 380 | 353 | 27 | 20 | 19–19 | 19–19 | NO |
