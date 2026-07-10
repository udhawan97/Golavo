# Free & open football data sources — verification sweep

**Verified:** 2026-07-10. **Method:** four-round discovery + adversarial verification — **46 sources** fetched and checked against their primary license/terms pages (40 in rounds 1–3, 6 more in round 4). Verdicts come from reading each source's actual license, not its marketing.

This extends the original licensing audit (openfootball, martj42, Wikidata, Wyscout/figshare, OpenLigaDB, football-data.org, API-Football, StatsBomb, Open-Meteo). The big result: several **genuinely open, redistributable** sources turned up that the first pass missed, and a whole **free-but-not-redistributable** tier came into focus.

## Three tiers

### Tier A — OPEN (free + an open license that permits redistribution) — safe for the open core

| Source | License | Data | Coverage | Fresh | Notes |
|---|---|---|---|---|---|
| **[DataHub.io core league CSVs](https://datahub.io/core/english-premier-league)** | **ODC-PDDL-1.0** (public domain) | results + **shots, corners, cards**, half-time, referee, odds | EPL 1993/94→**2025/26**, plus other leagues | **CURRENT** (~weekly) | ⭐ Best new find — open **and** current **and** has corners. Derived from football-data.co.uk, re-licensed PDDL; sanity-check the provenance. |
| **[ISDB (Open International Soccer DB, OSF)](https://osf.io/kqcye/)** | **CC0** | results only | 216,743 matches, 52 leagues / 35 countries, 2000/01–2017/18 | Stale (2017) | Built for ML; excellent historical training set. |
| **[footballcsv](https://footballcsv.github.io/)** | **CC0** | results (FT; HT sparse) | England tiers 1–5 + ES/DE/… | Stale (~2020/21) | Clean CSV historical archive. |
| **[European Soccer DB (Kaggle, hugomathien)](https://www.kaggle.com/datasets/hugomathien/soccer)** | **ODbL** (share-alike) | results + **lineups (coords)** + **events (goals/cards/corners)** + FIFA player/team ratings + odds | 11 EU leagues, 2008/09–2015/16 | Stale | ⭐ Has corners **and** lineups for model dev. Commercial use legally ambiguous (author's "no commercial" wish vs ODbL's grant); FIFA-rating provenance caveat. Treat like OpenLigaDB — **isolated** (share-alike). |
| **[DFL / Bassek et al. 2025 (Nature Sci Data)](https://www.nature.com/articles/s41597-025-04505-y)** | **CC-BY 4.0** | **tracking (1M+ frames) + event data** | elite (Bundesliga), ~2022, small sample | Static | ⭐ Genuinely open event **and** tracking data — but research-scale (a few matches). |
| **[DBpedia](https://www.dbpedia.org)** | CC-BY-SA-3.0 | reference facts (entities, relations) | all eras with Wikipedia articles | Quarterly (2025-06) | Complements Wikidata; note the ShareAlike copyleft. |
| **[SoccerMon (Zenodo)](https://zenodo.org/records/10033832)** | CC-BY 4.0 | women's athlete GPS/HR monitoring | Toppserien, 2020–21 | Static | Niche (fitness, not match data). |
| **[Transfermarkt datasets (davidcariboo/player-scores)](https://www.kaggle.com/datasets/davidcariboo/player-scores)** | **CC0** | 12 relational tables: games, **lineups**, **events (goals/cards/subs)**, appearances, valuations, transfers, players, clubs | 40+ comps incl. **WC 2026, Euro, Copa América, AFCON, Asian Cup**; ~79k games, 37k players | **CURRENT** (weekly auto-refresh) | ⭐⭐ Keystone find — CC0, current, with **lineups + events**. Transfermarkt-derived: license-laundering / provenance risk (facts are non-copyrightable, but Transfermarkt's ToS bars scraping). |
| **[football-matches-2025 (HF, tarekmasryo)](https://huggingface.co/datasets/tarekmasryo/football-matches-2025-dataset)** | CC-BY 4.0 | results, FT/HT scores, referee | top-5 + UCL, 2024/25 only (1,941) | Static | Derived from football-data.org; dual attribution required. |
| **[SoccerTrack v2 (atomscott)](https://atomscott.github.io/SoccerTrack-v2/)** | CC-BY 4.0 + MIT | tracking, ball-action spotting, 4K video | 10 amateur JP university matches | Static (2025) | Research/CV benchmark, not pro data. |
| **[Harvard Dataverse — national-team diversification](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/IMVEA1)** | CC0 | migration corridors / nationality changes | World Cup only, 1930–2018 | Static | Niche (no scores/fixtures). |
| **[Mendeley — Brazilian Série A (Czekster)](https://data.mendeley.com/datasets/thsvj4sycn/1)** | CC-BY 4.0 | results, attendance, standings | Brazil Série A, 2003–2019 | Static | Historical single-league. |

**Open context/reference (not football, but useful complements):**

- **Weather** (redistributable, unlike Open-Meteo's non-commercial *free API*): [Meteostat](https://dev.meteostat.net/) (CC-BY), [NOAA NCEI/GHCN](https://www.ncei.noaa.gov/access) (CC0), [ERA5/Copernicus](https://cds.climate.copernicus.eu/) (CC-BY), [NASA POWER](https://power.larc.nasa.gov/) (CC-BY), [DWD Open Data](https://opendata.dwd.de/) (CC-BY).
- **Venue geo/altitude**: [GeoNames](https://www.geonames.org/) (CC-BY, daily), OpenStreetMap via [Nominatim](https://nominatim.org/)/[Overpass](https://wiki.openstreetmap.org/wiki/Overpass_API) (ODbL, share-alike).

### Tier B — FREE TO FETCH, NOT OPEN (use per-user locally; never redistribute) — a new middle tier

Free (often keyless) but granting **no redistribution right**. The user fetches these onto their own machine and Golavo shows them locally, but the app never ships, exports, or re-publishes the data.

| Source | Data | Coverage | Fresh | Why not open |
|---|---|---|---|---|
| **[football-data.co.uk](https://www.football-data.co.uk/data.php)** | results + **shots, corners, cards**, odds | 11 leagues | **CURRENT** (2×/week) | No redistribution license (this is DataHub PDDL's upstream). |
| **[TheSportsDB](https://www.thesportsdb.com/)** | fixtures/results/tables/players/badges | broad | Current | Redistribution ambiguous/restricted; attribution required. |
| **[FPL Official API](https://fantasy.premierleague.com/api/bootstrap-static/)** | minutes, goals, assists, prices, ownership | PL only | Real-time | Proprietary, all rights reserved. |
| **[American Soccer Analysis API](https://app.americansocceranalysis.com/api/v1/__docs__/)** | **xG**, xPass, goals-added | MLS, NWSL, USL | Current | Informal attribution ask; no open grant. |
| **[ClubElo](http://clubelo.com/API)** | club Elo ratings (CSV) | top European clubs | Daily | No license stated → treat as not-redistributable. |
| **[soccerdata (Python, Apache-2.0 code)](https://soccerdata.readthedocs.io/)** | scraper for FBref/Understat/… | as upstream | n/a | The **code** is open; the **data** it pulls is not. |
| **[RSSSF](https://www.rsssf.org/)** | deep historical tables/results | worldwide | Actively updated | Copy-with-attribution, non-commercial only. |
| Commercial APIs w/ free trials/tiers | varies | broad (marketed) | current | Proprietary, mostly trial-only, not redistributable: Sportmonks, SoccersAPI, SportsDataIO, Entity Sports, Highlightly, FootyStats, Live-Score API, TheStatsAPI, API-Futebol, BSD. |

### Tier C — RESTRICTED / AVOID (scraping or ToS forbid the use we'd need)

- **FBref / Sports-Reference** — the richest *free* data (lineups, minutes, **xG**, scorers, manager records) but redistribution/mining prohibited and a hard 10-requests/minute cap.
- **Understat** — current **xG** for the top-5 + RPL, but an unofficial scrape with no license.
- **Sofascore**, **FotMob** — rich real-time (lineups, xG, corners) but explicitly forbid scraping/redistribution.
- **EasySoccerData** — code with a conflicting MIT/GPL license that scrapes Sofascore; data not safe to use.
- **sportsopendata.net** — CC-BY, but abandoned at 2016/17 — effectively unavailable.
- **eatpizzanot/soccer-dataset** — self-declares CC-BY 4.0 but it is **license-laundering** over API-Football + football-data.co.uk (whose ToS bar redistribution); broad stats + a *coarse* provider xG estimate for 128k fixtures, but the stated license is invalid. Avoid — and a cautionary example of the provenance risk that also touches DataHub-PDDL and the Transfermarkt datasets.

## Gap check — open, redistributable, AND current

| Data type | Status |
|---|---|
| Results / tables | ✅ improved — DataHub PDDL (current) + the CC0 backbone |
| **Corners / shots / cards** | ✅ **now open + current** via DataHub PDDL (was "unavailable"); also free-local via football-data.co.uk; historical via European Soccer DB (ODbL) |
| Club lineups / minutes | ✅ **now open + current** — Transfermarkt datasets (CC0, weekly) `game_lineups`; also historical via European Soccer DB; free-local via FBref/FPL (Transfermarkt-provenance caveat) |
| Scorers / events (club) | ✅ **now open + current** — Transfermarkt datasets (CC0) `game_events` goals/cards/subs; historical via European Soccer DB; free-local via FBref |
| Club **xG** | ❌ still no open+redistributable source — free-local only (Understat/FBref); research-scale open (DFL/SoccerTrack tracking); StatsBomb excluded; eatpizzanot's "xG" is coarse and its license invalid |
| Injuries / suspensions | ❌ no open source found (round 4 confirmed none) |
| Women's football | ❌ no dedicated open match/event source (only SoccerMon fitness data, SoccerTrack amateur) |

## Recommendation — adopt a three-tier data model

The single most useful outcome of this sweep: replace the old binary "open core vs BYOK" with **three** tiers, each legally isolated (enforced in CI like the ODbL guard):

1. **Open core** (redistributable, shippable): openfootball, martj42, Wikidata, DBpedia, ISDB, footballcsv, **Transfermarkt datasets (CC0 — current lineups + events + appearances)**, **DataHub PDDL (current results + corners/shots/cards)**, European Soccer DB (ODbL, isolated), DFL/SoccerTrack tracking (dev), weather (CC-BY), GeoNames/OSM. Flag the Transfermarkt/DataHub *provenance* risk explicitly (both re-license third-party-sourced facts).
2. **Local personal fetch** (free, NOT redistributable — new): football-data.co.uk, Understat, FPL, FBref (rate-limited), ClubElo, ASA — pulled to the user's machine, shown locally, never exported or re-published.
3. **BYOK keyed** (unchanged): football-data.org, API-Football.

This turns the earlier "xG and corners are unavailable" into a precise, honest picture: **corners are now open + current** (DataHub PDDL), and **xG is available free-locally** (Understat/FBref) though never redistributable — with clean legal separation between what Golavo *ships* and what a user *fetches for themselves*.
