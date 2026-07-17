---
title: Sources & licenses
description: Golavo's accepted sources, refresh boundaries, isolated overlays, and provenance enforcement.
---

Golavo's **code** is Apache-2.0. Data has its own license and storage boundary.
Every displayed source fact carries a source identity; derived context names its
input sources and formula version.

## Bundled and refreshable core data

| Source | Scope | License | Runtime behavior |
|---|---|---|---|
| [martj42/international_results](https://github.com/martj42/international_results) | men's senior full internationals, goalscorers, shootouts, former names | CC0-1.0 | bundled, refreshable, international seal→score source |
| [openfootball/worldcup.json](https://github.com/openfootball/worldcup.json) | World Cup fixtures, exact kickoff, round and venue context | CC0-1.0 | bundled co-source, refreshable; can corroborate settlement but conflicts fail closed |
| [openfootball/football.json](https://github.com/openfootball/football.json) | top-five European leagues | CC0-1.0 | bundled historical packs; refresh activates only files the upstream repository genuinely publishes for the current season |
| [openfootball/england](https://github.com/openfootball/england), [deutschland](https://github.com/openfootball/deutschland), [espana](https://github.com/openfootball/espana), [italy](https://github.com/openfootball/italy), [europe](https://github.com/openfootball/europe) | 2026-27 league schedules (Football.TXT), which football.json does not publish | CC0-1.0 | bundled co-sources of the league packs; supply fixture identity and the venue-local kickoff clock only — never a result, never training-eligible, and the clock carries no timezone upstream so kickoff precision stays day-level |
| [openfootball/champions-league](https://github.com/openfootball/champions-league) | Champions, Europa, and Conference League main competitions | CC0-1.0 | bundled historical browse/analytics packs; qualifiers excluded |

Each refresh first checks the upstream revision, then captures approved raw bytes under
a content hash. Parsers and schemas must pass before a complete generation can activate.
Activation is atomic and keeps the previous generation as last-known-good. A timeout,
offline state, cancellation, partial download, malformed row, or source conflict never
repoints the running index and never changes an existing seal.

Refresh is consent-gated. Golavo can check on launch and periodically **while the app is
open**, or only when you ask. It installs no daemon, Login Item, or LaunchAgent and makes
no closed-app monitoring claim. Current club fixtures remain unavailable unless an approved
source actually publishes a complete current-season file.

## Display-only context

| Source | Use | License / boundary |
|---|---|---|
| [GeoNames](https://www.geonames.org/) | 1,571 unique-exact city-country resolutions with coordinates, timezone and elevation; ambiguous and unresolved pairs stay unavailable | CC-BY-4.0 compact extracted pack with attribution |
| [Wikidata](https://www.wikidata.org/wiki/Wikidata:Licensing) | revision-pinned entity IDs, selected aliases and venue metadata | CC0 structured data; no fuzzy automatic identity merge |
| [Natural Earth](https://www.naturalearthdata.com/) | lightweight offline route basemap | public domain |

Distance, local kickoff, rest and travel are deterministic display context. Missing or
conflicting coordinates remain visible as unavailable; none of these values is a model input.

## Optional ODbL overlay

[OpenLigaDB](https://www.openligadb.de/) is an optional, keyless, per-user overlay under
ODbL-1.0. Golavo ships the adapter and license disclosure, **not OpenLigaDB response bytes**.
The user must accept the disclosure before fetching allowlisted current-season Bundesliga
1/2/3 or DFB-Pokal data.

Raw responses, receipts, the SQLite read model, manifests, attribution, and license notice
live under the separate `overlays/openligadb` Application Support root. The v1 overlay is
display-only. It cannot enter the CC0 match warehouse, source packs, model training,
calibration, forecasts, settlements, redistributable exports, or bundled artifacts. Teams
keep OpenLigaDB source identities; Golavo performs no fuzzy or automatic merge. Conflicts
fail closed. Disabling or deleting the overlay removes its local generations without
touching forecasts, packs, picks, follows, or corrections.

## Isolated attributed research

The Fjelstul World Cup Database is pinned under CC-BY-SA-4.0 and read only by the facts
layer. The compact Pappalardo/Wyscout CC-BY-4.0 pack contains team-level summaries for
seven competition/era slices; raw events and player identities do not ship. Both remain
outside the core match index and model training. Golavo's disclosed “research xT” is a
12×8 transition calculation, not observed xG.

Optional match research is source-selected, not an ingestion feed. Wikimedia discovery
may suggest pages or entities; after explicit selection Golavo captures permitted source text, URL,
retrieval time and hash, then routes extracted values into the untrusted local correction
queue. DuckDuckGo HTML scraping is disabled. Search never makes a fact authoritative.

## Enforcement

The registry records source ID, license class, attribution, approved hosts/paths,
retention and correction rules. CI validates manifests and hashes, generates third-party
notices, walks SQLite schemas and JSON artifacts, forbids cross-namespace source IDs, and
runs contamination tests across core indexes, training rows, calibration, exports and
packaging. The shell grep remains a fast lint; it is not the only isolation control.

## Rejected dependencies

Golavo does not add adapters for Transfermarkt-derived Kaggle datasets, DataHub football
mirrors, Understat, FBref, Sofascore, FotMob, unofficial FPL endpoints, European Soccer DB,
or `eatpizzanot`. A downstream license label does not cure incompatible upstream scraping
or database-right terms. Paid APIs and required user keys are not product dependencies.
Weather stays blocked until a lawful historical source preserves what was forecast before
kickoff; observed weather is not an acceptable substitute.

## Non-affiliation

Golavo is not affiliated with, endorsed by, or sponsored by FIFA, UEFA, any league, club,
or competition. Competition names are used factually to identify matches. See
[Legal & brand use](/Golavo/legal/).
