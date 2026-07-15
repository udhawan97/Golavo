# Third-party notices

Golavo's own code is licensed Apache-2.0 (see `LICENSE`). This file, generated
from `data/sources/registry.json` by `scripts/gen_third_party_notices.py`, records
the data sources Golavo carries, plans, or has rejected. Software dependency
notices ship as an SPDX/CycloneDX SBOM alongside each release.

> Do not edit by hand — run `python scripts/gen_third_party_notices.py`.

## Bundled data (public domain / CC0)

### martj42/international_results — **bundled**

- Source: https://github.com/martj42/international_results
- Contributors: Mart Jürisoo
- License: CC0-1.0 (https://github.com/martj42/international_results/blob/master/LICENSE)
- Attribution: International football results from martj42/international_results (Mart Jürisoo), CC0-1.0.
- Notes: Bundled and seal-eligible. Sole forward-seal training source. Date-only; exact kickoff requires the worldcup-json overlay.

### openfootball/champions-league — available, not bundled

- Source: https://github.com/openfootball/champions-league
- Contributors: Gerald Bauer, openfootball contributors
- License: CC0-1.0 (https://github.com/openfootball/champions-league/blob/master/LICENSE.md)
- Attribution: European club competition data from openfootball/champions-league (Gerald Bauer and contributors), CC0-1.0.
- Notes: Registered for Phase 2, not bundled yet. Every imported competition-season must pass fixture/result completeness and format-era checks before Golavo marks it available.

### openfootball/euro — available, not bundled

- Source: https://github.com/openfootball/euro
- Contributors: Gerald Bauer, openfootball contributors
- License: CC0-1.0 (https://github.com/openfootball/euro/blob/master/LICENSE.md)
- Attribution: European Championship data from openfootball/euro (Gerald Bauer and contributors), CC0-1.0.
- Notes: Registered for Phase 2, not bundled yet. Used only after edition completeness and rule-version validation; martj42 remains the historical international results source.

### openfootball/football.json — **bundled**

- Source: https://github.com/openfootball/football.json
- Contributors: Gerald Bauer, openfootball contributors
- License: CC0-1.0 (https://github.com/openfootball/football.json/blob/master/LICENSE.md)
- Attribution: Club football results from openfootball/football.json (Gerald Bauer and contributors), CC0-1.0.
- Notes: Bundled, search/backtest only (five leagues share one source_id, so not seal-eligible). Naive local kickoff time; club rows carry kickoff_precision=day.

### openfootball/worldcup.json — **bundled**

- Source: https://github.com/openfootball/worldcup.json
- Contributors: Gerald Bauer, openfootball contributors
- License: CC0-1.0 (https://github.com/openfootball/worldcup.json/blob/master/LICENSE.md)
- Attribution: World Cup fixtures and kickoff times from openfootball/worldcup.json (Gerald Bauer and contributors), CC0-1.0.
- Notes: Bundled as a fixture/kickoff co-source inside the refreshed internationals pack: supplies the World Cup fixtures martj42 has not published yet plus exact kickoff times. Excluded from model training (martj42 remains the sole training source). A user-authorized post-match check may also use its pinned, hashed final score to settle a World Cup seal when martj42 still reports NA/NA; if both sources publish and disagree, settlement fails closed. W###/L### placeholder fixtures are rejected until the bracket resolves.

## Bundled enrichment data (CC BY)

### GeoNames — available, not bundled

- Source: https://www.geonames.org/export/
- Contributors: GeoNames.org
- License: CC-BY-4.0 (https://download.geonames.org/export/dump/readme.txt)
- Attribution: Geographic data from GeoNames (geonames.org), licensed CC BY 4.0.
- Notes: Planned enrichment source. Bulk dumps only, no runtime web-service dependency. Commercial use permitted with attribution.

### Natural Earth — available, not bundled

- Source: https://www.naturalearthdata.com/
- Contributors: Tom Patterson, Nathaniel Vaughn Kelso, Natural Earth contributors
- License: PUBLIC-DOMAIN (https://www.naturalearthdata.com/about/terms-of-use/)
- Attribution: Made with Natural Earth.
- Notes: Registered for Phase 3, not bundled yet. Golavo will pin one simplified release and hash; no online tile service or third-party basemap is required.

### Wikidata — available, not bundled

- Source: https://www.wikidata.org/wiki/Wikidata:Licensing
- Contributors: Wikidata contributors
- License: CC0-1.0 (https://www.wikidata.org/wiki/Wikidata:Licensing)
- Attribution: Structured data from Wikidata (CC0); we credit it voluntarily as 'Data from Wikidata'.
- Notes: Later-if-needed. Structured data is CC0; prose (CC BY-SA) and Commons media (per-file) are excluded. Never auto-merge identities from a similarity match.

## Optional isolated packs — ODbL (share-alike)

### OpenLigaDB — optional download, isolated pack

- Source: https://www.openligadb.de/
- Contributors: Marcel Siegel, OpenLigaDB community
- License: ODbL-1.0 (https://www.openligadb.de/lizenz)
- Attribution: Datenquelle: OpenLigaDB (www.openligadb.de) — Open Database License (ODbL) v1.0.
- Notes: Optional isolated ODbL pack. A redistributed derivative database must itself be ODbL and ship the license URI; must never merge into the CC0/CC-BY core or the CC-BY-SA pack. Single-operator hobby service — feature must tolerate its permanent absence.

## Optional isolated packs — CC BY-SA (share-alike)

### Fjelstul World Cup Database — **vendored, isolated pack**

- Source: https://github.com/jfjelstul/worldcup
- Contributors: Joshua C. Fjelstul
- License: CC-BY-SA-4.0 (https://creativecommons.org/licenses/by-sa/4.0/legalcode)
- Attribution: Fjelstul World Cup Database v1.2.0 © 2023 Joshua C. Fjelstul, Ph.D., CC BY-SA 4.0; modifications noted.
- Citation key: `fjelstul2023worldcup` (see CITATIONS.bib)
- Notes: Vendored as an isolated facts-only CC-BY-SA pack. Grant lives only in README+DESCRIPTION (no LICENSE file), no v1.2.0 tag — pinned at commit f942c6b with README+DESCRIPTION retained as license evidence. NEVER substitute WorldCups.ai downloads (CC BY-NC-SA). Golavo uses only the men's 1930–2022 history.

## Optional research packs (historical event/tracking data)

### IDSSE — integrated spatiotemporal + event data — optional download, isolated pack

- Source: https://springernature.figshare.com/articles/dataset/An_integrated_dataset_of_spatiotemporal_and_event_data_in_elite_soccer/28196177
- Contributors: Manuel Bassek, Robert Rein, Hendrik Weber, Daniel Memmert
- License: CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/)
- Attribution: IDSSE dataset, provided with authorization of the Deutsche Fußball Liga (DFL); Bassek et al., Sci Data 12:195 (2025), CC BY 4.0.
- Citation key: `bassek2025idsse` (see CITATIONS.bib)
- Notes: Research-only (pipeline validation). 2.63 GB for 7 matches — not a user-facing pack. Attribution must name DFL and cite the paper.

### Pappalardo/Wyscout public soccer event dataset — optional download, isolated pack

- Source: https://figshare.com/collections/Soccer_match_event_dataset/4415000
- Contributors: Luca Pappalardo, Paolo Cintia, Alessio Rossi, Emanuele Massucco, Paolo Ferragina, Dino Pedreschi, Fosca Giannotti
- License: CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/)
- Attribution: Event data: Pappalardo et al., Sci Data 6:236 (2019), CC BY 4.0 (collected by Wyscout).
- Citation key: `pappalardo2019dataset` (see CITATIONS.bib)
- Notes: Optional research pack. Historical team-level research only; never blended into live models or simulations. Labeled by exact competition and era, never 'observed xG'. Raw events are optional; compact derived artifacts may be bundled with attribution and modification notices.

### SkillCorner Open Data — optional download, isolated pack

- Source: https://github.com/SkillCorner/opendata
- Contributors: SkillCorner, PySport
- License: MIT (https://github.com/SkillCorner/opendata/blob/master/LICENSE)
- Attribution: Tracking data courtesy of SkillCorner and PySport (SkillCorner Open Data, MIT).
- Notes: Optional research pack. Preserve documented limits (~97% ID accuracy; extrapolated frames flagged).

## Evaluated but blocked (not used)

### martj42/womens-international-results

- Source: https://github.com/martj42/womens-international-results
- Contributors: Mart Jürisoo
- License: NONE
- Recheck by: 2026-10-01
- Notes: BLOCKED: no LICENSE file as of the verified date (default all-rights-reserved). Do not use or redistribute. Recheck for an added open license.

### Meteostat

- Source: https://dev.meteostat.net/
- Contributors: Meteostat, Deutscher Wetterdienst, NOAA, ECCC
- License: UNRESOLVED (https://dev.meteostat.net/license)
- Recheck by: 2026-10-01
- Notes: BLOCKED: /license states CC BY 4.0 but the live /faq states CC BY-NC 4.0 — a contradiction that must be resolved in writing before adoption. Also no historical-FORECAST archive exists, so weather can only ever be context, never a backtested pre-match feature.

## Reviewed and rejected (not used)

### ClubElo

- Source: http://clubelo.com/
- Contributors: ClubElo
- License: NONE
- Notes: REJECTED: publishes no license or terms of any kind. Free access is not a redistribution grant.

### football-data.org

- Source: https://www.football-data.org/
- Contributors: Freitag Web Tec UG
- License: PROPRIETARY-API-TERMS (https://www.football-data.org/about)
- Notes: REJECTED: proprietary API service with a post-cancellation data restriction. Free access is not openly licensed redistributable data.

### Open-Meteo (hosted free API)

- Source: https://open-meteo.com/
- Contributors: Open-Meteo
- License: CC-BY-4.0-data-AGPL-3.0-source (https://open-meteo.com/en/terms)
- Notes: REJECTED as a default dependency: the hosted free API tier is non-commercial only. Only ever a user-supplied optional adapter with disclosed terms.

### StatsBomb Open Data

- Source: https://github.com/statsbomb/open-data
- Contributors: StatsBomb
- License: PROPRIETARY-USER-AGREEMENT (https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf)
- Notes: REJECTED: user agreement forbids redistribution and commercial use, is revocable, and mandates logo attribution. Not an open-data license.
