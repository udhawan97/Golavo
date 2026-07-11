---
title: Sources & licenses
description: Phase 0's accepted source, manifest contract, and rejected data dependencies.
---

Golavo's **code** is Apache-2.0. Data packs are licensed separately. Phase 0 accepts one data source:

| Source | Scope | License | Pinning | Phase 0 status |
|---|---|---|---|---|
| [martj42/international_results](https://github.com/martj42/international_results) | men's senior full-international results, goalscorers, shootouts, former names | CC0-1.0 | exact upstream Git commit + per-file SHA-256 | ✅ vendored sourcepack |

The pack manifest records `source_id`, upstream URL and commit, retrieval time, every filename and SHA-256 digest, and the pack license. The repository vendors a copy of the CC0 text. Provenance validation hashes the bytes again in CI.

## Rejected dependencies

Golavo does not add adapters for Transfermarkt-derived Kaggle datasets, DataHub football mirrors, Understat, FBref, Sofascore, FotMob, unofficial FPL endpoints, European Soccer DB, or `eatpizzanot`. A downstream CC0/PDDL label does not cure an upstream source's scraping terms or database-right provenance; treating it as clean would be provenance laundering.

Football-Data.org, API-Football, OpenFootball, Wikidata, Wyscout, weather sources, and ODbL overlays are not Phase 0 dependencies. Future adoption requires a new evidence and license review; it is not implied by the design docs.

## What the ODbL check does

`scripts/check_license_isolation.sh` is a **basic grep lint** for a few forbidden ODbL references. It is not legal isolation enforcement and must not be described as proof that database rights cannot mix.

## Non-affiliation

Golavo is not affiliated with, endorsed by, or sponsored by FIFA, UEFA, any league, club, or competition. Competition names are used factually to identify matches. See [Legal & brand use](/Golavo/legal/).
