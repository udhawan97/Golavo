---
title: Sources & licenses
description: The field-level license matrix for every data source, with attribution requirements. Verified against primary sources on 2026-07-09.
---

Golavo does not redistribute proprietary data. Only public-domain / open sources are built into the open core. Everything below was verified against the source's own primary page/license on **2026-07-09**.

## License matrix

| Source | License | Fetch | Cache | Redistribute raw | Train models | Attribution | In product |
|---|---|---|---|---|---|---|---|
| [openfootball](https://github.com/openfootball/football.json) | CC0-1.0 | ✅ | ✅ | ✅ | ✅ | none | ✅ |
| [martj42/international_results](https://github.com/martj42/international_results) | CC0-1.0 | ✅ | ✅ | ✅ | ✅ | none | ✅ |
| [Wikidata](https://www.wikidata.org/wiki/Wikidata:Licensing) (structured data) | CC0-1.0 | ✅ | ✅ | ✅ | ✅ | none | ✅ |
| [Wyscout events](https://figshare.com/collections/Soccer_match_event_dataset/4415000/5) | CC BY 4.0 | ✅ | ✅ | ✅ + credit | ✅ + credit | required | 🔬 dev only |
| [Open-Meteo](https://open-meteo.com/en/terms) | data CC BY 4.0; free API non-commercial | ✅ | ✅ | ✅ + credit | ✅ | required | ✅ optional |
| [OpenLigaDB](https://www.openligadb.de) | ODbL 1.0 (share-alike) | ✅ | ✅ | ✅ under ODbL | ⚠️ share-alike risk | required + notice | 🧱 isolated overlay |
| [Football-Data.org](https://www.football-data.org/) | proprietary ToS | 🔑 | ⚠️ unaddressed | ❌ | ⚠️ unaddressed | required string | 🔑 BYOK |
| [API-Football](https://www.api-football.com/) | proprietary ToS | 🔑 | ⚠️ unaddressed | ❌ resale banned | ⚠️ unaddressed | none stated | 🔑 BYOK |
| [StatsBomb Open Data](https://github.com/statsbomb/open-data) | restrictive user agreement | ✅ | ✅ | ❌ | ❌ (commercial derived analysis banned) | logo required | 🚫 excluded |

## Attribution strings (shown in-app on the screens that use them)

- **Football-Data.org** (when you supply a key): *"Football data provided by the Football-Data.org API."*
- **Open-Meteo**: *"Weather data by Open-Meteo.com"* (CC BY 4.0).
- **Wyscout**: cite Pappalardo, L. et al. (2019), *A public data set of spatio-temporal match events in soccer competitions*, Scientific Data 6, 236.
- **OpenLigaDB**: data under the Open Database License (ODbL) 1.0.

## Why some things are the way they are

### OpenLigaDB is kept physically isolated
OpenLigaDB's data is under the **ODbL**, whose share-alike terms would attach to any combined database it is merged into. Golavo keeps it in a separate pack and a separate database file, and CI blocks any join into the CC0 core. It is an optional Bundesliga/DFB-Pokal overlay only.

### StatsBomb is excluded from the product
StatsBomb's public-data user agreement prohibits redistributing the data and **commercially exploiting even derived analysis**, and asks that any published analysis carry the StatsBomb logo. Golavo does not bundle it, redistribute it, or train any shipped model weights on it. (Research use, outside this product, remains possible under their terms with attribution.)

### Free access ≠ open data
Football-Data.org and API-Football free tiers are *gratis, revocable, and non-redistributable*. Their data is rendered only in the key-holder's private local session, is never exported by default, and is purged when the key is removed. Football-Data.org additionally forbids referencing its data after a subscription is cancelled.

## Non-affiliation

Golavo is not affiliated with, endorsed by, or sponsored by FIFA, UEFA, any league, club, or competition. Competition names are used factually to identify matches. See [Legal & brand use](/Golavo/legal/).
