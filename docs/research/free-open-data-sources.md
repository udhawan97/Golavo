# Free & open football data sources — verification sweep

**Verified:** 2026-07-10. **Method:** four-round discovery + adversarial verification — **46 sources** fetched and checked against their primary license/terms pages (40 in rounds 1–3, 6 more in round 4). Verdicts come from reading each source's actual license, not its marketing.

This is a historical research sweep, corrected by the accepted-core provenance decision. A license label on a downstream mirror does not establish that its upstream collection was lawful. The accepted international core therefore uses only `martj42/international_results`; other entries below remain research candidates or rejected dependencies unless a later audit explicitly accepts them.

**Implementation update (2026-07-15):** OpenLigaDB passed a fresh primary-source
license/API check and is now implemented as an optional, per-user ODbL overlay
for current-season `bl1`, `bl2`, `bl3`, and `dfb` display context. It remains off
by default, ships no response bytes, stores raw/derived data outside the CC0
warehouse, performs no fuzzy identity merge, and cannot feed training, sealing,
settlement, calibration, artifacts, or exports. See ADR-0005 and
`packs/overlay-odbl/policy.json`.

## Three tiers

### Tier A — OPEN (free + an open license that permits redistribution) — safe for the open core

| Source | License | Data | Coverage | Fresh | Notes |
|---|---|---|---|---|---|
| **[ISDB (Open International Soccer DB, OSF)](https://osf.io/kqcye/)** | **CC0** | results only | 216,743 matches, 52 leagues / 35 countries, 2000/01–2017/18 | Stale (2017) | Built for ML; excellent historical training set. |
| **[footballcsv](https://footballcsv.github.io/)** | **CC0** | results (FT; HT sparse) | England tiers 1–5 + ES/DE/… | Stale (~2020/21) | Clean CSV historical archive. |
| **[European Soccer DB (Kaggle, hugomathien)](https://www.kaggle.com/datasets/hugomathien/soccer)** | **ODbL** (share-alike) | results + **lineups (coords)** + **events (goals/cards/corners)** + FIFA player/team ratings + odds | 11 EU leagues, 2008/09–2015/16 | Stale | ⭐ Has corners **and** lineups for model dev. Commercial use legally ambiguous (author's "no commercial" wish vs ODbL's grant); FIFA-rating provenance caveat. Treat like OpenLigaDB — **isolated** (share-alike). |
| **[DFL / Bassek et al. 2025 (Nature Sci Data)](https://www.nature.com/articles/s41597-025-04505-y)** | **CC-BY 4.0** | **tracking (1M+ frames) + event data** | elite (Bundesliga), ~2022, small sample | Static | ⭐ Genuinely open event **and** tracking data — but research-scale (a few matches). |
| **[DBpedia](https://www.dbpedia.org)** | CC-BY-SA-3.0 | reference facts (entities, relations) | all eras with Wikipedia articles | Quarterly (2025-06) | Complements Wikidata; note the ShareAlike copyleft. |
| **[SoccerMon (Zenodo)](https://zenodo.org/records/10033832)** | CC-BY 4.0 | women's athlete GPS/HR monitoring | Toppserien, 2020–21 | Static | Niche (fitness, not match data). |
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
- **Transfermarkt-derived datasets (davidcariboo/player-scores)** — **REJECTED**. A downstream CC0 declaration does not cure Transfermarkt's upstream scraping/ToS and database-provenance risk. Shipping it would launder provenance through the mirror.
- **DataHub football mirrors** — **REJECTED**. A downstream PDDL declaration does not cure the upstream football-data.co.uk terms or establish database rights. Shipping the mirror would launder provenance.
- **European Soccer DB (hugomathien)** — **REJECTED** because its mixed upstream provenance is not sufficiently documented for the accepted source pack.

## Gap check — open, redistributable, AND current

| Data type | Status |
|---|---|
| Results / tables | ✅ men's senior full internationals only via martj42 CC0; no accepted club source |
| **Corners / shots / cards** | ❌ no accepted open source |
| Club lineups / minutes | ❌ no accepted open source |
| Scorers / events (club) | ❌ no accepted open source |
| Club **xG** | ❌ still no open+redistributable source — free-local only (Understat/FBref); research-scale open (DFL/SoccerTrack tracking); StatsBomb excluded; eatpizzanot's "xG" is coarse and its license invalid |
| Injuries / suspensions | ❌ no open source found (round 4 confirmed none) |
| Women's football | ❌ no dedicated open match/event source (only SoccerMon fitness data, SoccerTrack amateur) |

## Accepted-core decision — one international source pack

The accepted-core decision supersedes the earlier three-tier recommendation:

1. **Accepted open core:** a pinned `martj42/international_results` snapshot for men's senior full internationals.
2. **Rejected:** Transfermarkt-derived Kaggle data, DataHub football mirrors, Understat, FBref, Sofascore, FotMob, unofficial FPL endpoints, European Soccer DB, and `eatpizzanot`.
3. **Not accepted by this research decision:** club adapters, BYOK sources, AI, lineups, corners, scorers, and xG. Later implementations require their own provenance decision.

The original ODbL grep remains a cheap lint, but it is now backed by
`scripts/validate_license_isolation.py`: machine-readable policy checks, AST
import boundaries, registry/index/package audits, and contamination canaries.
Any future data source still requires a fresh provenance review before code or
adapters are added.
