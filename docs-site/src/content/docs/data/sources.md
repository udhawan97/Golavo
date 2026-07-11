---
title: Sources & licenses
description: Golavo's accepted CC0 sources, the manifest contract, and rejected data dependencies.
---

Golavo's **code** is Apache-2.0. Data packs are licensed separately. Golavo accepts two CC0 upstreams, each vendored as pinned sourcepacks:

| Source | Scope | License | Pinning | Status |
|---|---|---|---|---|
| [martj42/international_results](https://github.com/martj42/international_results) | men's senior full-international results, goalscorers, shootouts, former names | CC0-1.0 | exact upstream Git commit + per-file SHA-256 | ✅ vendored (internationals, forward loop) |
| [openfootball/football.json](https://github.com/openfootball/football.json) | top-5 European leagues — EPL, La Liga, Bundesliga, Serie A, Ligue 1 | CC0-1.0 | exact upstream Git commit + per-file SHA-256 | ✅ vendored (historical, one pack per league) |

The pack manifest records `source_id`, upstream URL and commit, retrieval time, every filename and SHA-256 digest, and the pack license. The repository vendors a copy of the CC0 text. Provenance validation hashes the bytes again in CI.

## Rejected dependencies

Golavo does not add adapters for Transfermarkt-derived Kaggle datasets, DataHub football mirrors, Understat, FBref, Sofascore, FotMob, unofficial FPL endpoints, European Soccer DB, or `eatpizzanot`. A downstream CC0/PDDL label does not cure an upstream source's scraping terms or database-right provenance; treating it as clean would be provenance laundering.

Football-Data.org, API-Football, Wikidata, Wyscout, weather sources, and ODbL overlays are not current dependencies. Future adoption requires a new evidence and license review; it is not implied by the design docs. (OpenFootball has passed a per-league coverage audit and is vendored for historical seasons only — see [Coverage](/Golavo/data/coverage/).)

## What the ODbL check does

`scripts/check_license_isolation.sh` is a **basic grep lint** for a few forbidden ODbL references. It is not legal isolation enforcement and must not be described as proof that database rights cannot mix.

## Non-affiliation

Golavo is not affiliated with, endorsed by, or sponsored by FIFA, UEFA, any league, club, or competition. Competition names are used factually to identify matches. See [Legal & brand use](/Golavo/legal/).
