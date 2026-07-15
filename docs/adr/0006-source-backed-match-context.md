# ADR-0006: isolate source-backed match context from forecasting

Status: accepted for implementation, 2026-07-15.

Golavo may enrich match pages with a compact, bundled context pack derived from
GeoNames, Natural Earth and a reviewed allowlist of Wikidata entities. Context is
display-only. It cannot enter model inputs, training data, calibration,
settlement, sealed forecast artifacts or redistributable match exports.

Every displayed source fact carries a source record identity and immutable
snapshot or revision. Every calculated fact carries its input claim identities,
formula identifier and algorithm version. The application never labels a city
coordinate or elevation as a stadium fact, never calls a great-circle distance
actual team travel and never calls a date-only calendar gap exact rest.

Entity reconciliation fails closed. A stable upstream identifier may reconnect
only to the same previously reviewed identity. Exact-name collisions, fuzzy
matches, changed identifiers and materially conflicting coordinates remain
unavailable until a checked-in resolution record accepts or rejects them. Newer
data does not win merely because it is newer.

Wikidata access is a maintainer-only build operation over an explicit QID and
property allowlist. Individual entity responses are pinned to revisions and
retained as immutable evidence. No Wikidata, GeoNames, map-tile or geocoder
request is made by the installed application. Natural Earth remains a compact
offline basemap with a textual alternative.

The context pack is a read-only enrichment side table. It cannot read the
OpenLigaDB overlay or contain OpenLigaDB identifiers or response bytes. Runtime
cache keys include both the active match-index fingerprint and context-pack hash,
so an approved-source generation repoint cannot serve stale derived context.

No helper, LaunchAgent, daemon or closed-app context refresh is included. A new
fixture not covered by the bundled reviewed pack reports an honest unavailable
state until a later Golavo release updates that pack.
