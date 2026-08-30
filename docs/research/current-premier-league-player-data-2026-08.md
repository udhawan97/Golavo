# Current Premier League and player-analysis data

**Verified:** 2026-08-29. **Scope:** the 2026/27 Premier League and player
analysis across the Premier League, Bundesliga, La Liga, Serie A and Ligue 1.
This is a conservative product-and-provenance assessment of primary source
documentation and first-party repositories. It is not legal advice.

## Decision

Golavo can activate the 2026/27 Premier League schedule and results after its
consent-aware OpenFootball refresh validates and certifies all five top-flight
schedules. Richer player detail should be a separate, user-triggered Sportmonks
Football API v3 panel using the user's own token. It must remain attributed,
display-only, absent by default and outside forecasting, calibration, sealing,
settlement, AI evidence and export.

No reviewed source supports bundling current top-five-league player performance
data. The technically rich alternatives either withhold publication rights,
conflict with durable local records, prohibit commercial use/redistribution, or
cover old/research-only seasons.

| Source | Decision | Current-season and field fit | Rights and delivery boundary | Forecast / calibration role |
|---|---|---|---|---|
| Existing `openfootball/{england,deutschland,espana,italy,europe}` plus `openfootball/football.json` | **Approve now** through the existing certified refresh only | Exact 2026/27 top-five files now exist. Matchday/round, date, venue-local clock without timezone, teams and score once played. No player data, venue, referee, lineups, injuries, events or xG. | CC0. May be pinned, bundled, refreshed and redistributed under the existing approved paths and all-or-nothing activation contract. | Completed result rows may retain the already-approved training role. Unplayed rows do not train; one club result source cannot settle a forecast. |
| `openfootball/players` | **Defer** | Name, position, height, birth date and birthplace by country; no current club/squad mapping, appearances, match events, performance statistics or stated stable player IDs. | CC0 and bundle-capable in principle, but identity and coverage are not yet certified. | None unless a later source decision defines a frozen, reproducible identity mapping and training purpose. |
| Sportmonks Football API v3 | **Approve as isolated / BYOK display-only** | Top-five competition pages advertise fixtures, lineups, events, injuries, suspensions, player/match stats and optional xG. The public Premier League page still says 2025/26, so a live token must prove each 2026/27 season and field. | Proprietary subscription; terms permit apps, storage and transfer but prohibit direct feed resale. Use a per-user token, foreground match fetch, no provider media, no bundled key/data, and initially no stored response bytes. | **None.** Do not use Sportmonks predictions, odds, xG or player facts in models, calibration, scoring, seals, settlement, AI evidence or exports. A future model role needs a separate written data agreement and reproducibility review. |
| football-data.org v4 | **Reject** under standard terms | All five leagues are in the advertised free coverage; paid tiers expose squads, lineups, goals, cards, substitutions, top scorers and limited match/player aggregates. It is materially thinner than Sportmonks for player analysis. | API key, visible attribution and plan-specific limits. Standard terms say obtained football data cannot be referenced after cancellation, which conflicts with durable local provenance. | None without a custom agreement granting post-cancellation retention/reference and model rights. |
| API-Football | **Reject** | Excellent technical fit: all five leagues, numeric IDs, lineups, injuries, events, detailed player statistics, predictions and odds; per-season coverage flags must still be checked. | Its terms expressly say the service does not grant the right to use or publish data in an app/site/product and requires permission from competent rights holders. | None until Golavo has written publication rights for this exact product and separately approved model rights. |
| StatsBomb Open Data | **Reject** | Selected historical competitions only; the repository has no 2026/27 top-five coverage. It offers matches, lineups, event JSON and some 360 data. | The user agreement forbids distribution/reproduction and commercial exploitation of the data or derived analysis, is revocable and disclaims completeness. | None in Golavo's shipped product, bundle or commercial model. |
| Pappalardo/Wyscout public event dataset | **Approve now: retain existing isolated research pack** | 2017/18 top-five leagues plus World Cup 2018 and Euro 2016: matches, players, teams, referees and 3.25M events. Not current. | CC BY 4.0 at the first-party Figshare collection. Golavo already redistributes only an attributed derived research pack, not raw player identities/events. | No live-model, current-form or observed-xG claim. A new model use is outside this decision. |
| SkillCorner Open Data | **Approve now: retain existing isolated research pack** | Ten 2024/25 Australian A-League matches, 10fps broadcast tracking, dynamic events, phases and selected season aggregates. Not a top-five/current source. | MIT first-party repository. Preserve its stated extrapolation and approximately 97% identity-quality limitations. | Research/demo only; no current top-five forecast input. |
| Official Premier League site, including public statistics/Fantasy endpoints | **Reject scraping** | Public 2026/27 match/player pages are useful to a person, but do not constitute a data license or documented product API. | Terms reserve copyright/database rights and prohibit commercial reuse, reproduction, redistribution and creating a database without written approval. `robots.txt` is not a rights grant. | None. Link to the official homepage for human reference; do not scrape pages or undocumented endpoints. |

`Approve now` means the named boundary is approved under Golavo's documented
source policy, compatible with its architecture and supported by the cited
license/terms. It does **not** prove that all possible third-party rights have
been cleared, or approve an uncatalogued download, new scraper, new training
feature or community mirror.

Implementation order:

1. Certify and activate the five OpenFootball 2026/27 schedules through the
   existing refresh flow.
2. Add a Sportmonks connection-time capability probe for the user's exact
   top-five league/season entitlements and metric groups.
3. Render only covered `Player Lens` groups for an unambiguously mapped match;
   keep every absent or disallowed group visibly unavailable.

### Delivery and reliability facts

| Source | Authentication / current cost | Published request limit and freshness | Identity / correction quality |
|---|---|---|---|
| OpenFootball current-season repositories | No source key or fee; Golavo fetches only after its own consent setting permits a refresh | Static GitHub files; no upstream SLA or football-specific rate/freshness promise. Golavo's configured check interval is 24 hours. | No published upstream fixture/team/player IDs or correction SLA. Golavo pins a commit, hashes bytes, mints canonical identities and rejects unsafe diffs. |
| OpenFootball players | No source key or fee; static CC0 repository that is storage- and redistribution-capable in principle | Static GitHub files; no upstream SLA, systematic current-squad promise or correction cadence. | No documented stable player IDs or correction guarantee; names alone cannot be promoted into Golavo identities. |
| Sportmonks v3 | User API token. Advertised €29/€99/€249 monthly Starter/Growth/Pro tiers; xG/history can cost extra. | Pricing currently advertises 2,000/2,500/3,000 requests per entity per hour. Response rate metadata and 429 are authoritative; live/stat/xG timing varies by package and field. | Numeric league, season, fixture, team, player, position and metric-type IDs; update/deletion/correction feeds exist, but accuracy and availability are not guaranteed. |
| football-data.org v4 | API key. Free; then advertised €12/€29/€49/€99/€199 monthly tiers plus €15 statistics/odds add-ons. | Free pricing says 10 requests/minute; higher plan limits differ and the policy summary is not fully aligned with pricing. Scores can be delayed on free. | Unique numeric competition, season, match, team and person IDs; UTC and null semantics are documented, but no immutability guarantee was found. Post-cancellation reference restriction defeats durable correction/provenance history. |
| API-Football | `x-apisports-key`. Advertised 100 requests/day free; $19/$29/$39 monthly at 7,500/75,000/150,000 daily. | Plan response headers govern daily/per-minute allowance. Guide targets 15–60 seconds for live events, one minute for stats, four hours for injuries and one hour for predictions; terms make no guarantee. | Numeric league, season, fixture, team and player IDs plus season coverage flags; flags do not guarantee every field for every match. Rights fail before technical acceptance. |
| StatsBomb Open Data | No key or price; static first-party GitHub repository | No data SLA or football-specific rate promise; selected snapshots are updated at the publisher's discretion. | Numeric competition/season/match/player/event relationships within the dataset; access and use are revocable and no completeness warranty is given. |
| Pappalardo/Wyscout Figshare | No key or price for the frozen collection | Static 2017/18-era research collection; no live refresh or correction SLA. | Frozen numeric match/team/player/event relationships, not a current cross-provider identity contract. |
| SkillCorner Open Data | No key or price for the frozen repository | Static ten-match sample; no live refresh or correction SLA. | Match-scoped tracking identities with explicit extrapolation flags and approximately 97% player identification, not a production global player identity service. |
| Official Premier League website | Public human website; no documented product API, plan or product key | No API quota/SLA. Terms expressly disclaim that statistics are accurate, complete or current. | Page URLs/names are not an API identity contract; corrections and schema stability are undocumented. |

## Current Golavo capability versus newly observed upstream data

Golavo's [source registry](../../data/sources/registry.json) and
[ADR-0004](../adr/0004-approved-source-refresh.md) already allow exactly one
current-season path from each OpenFootball country repository plus the five
top-flight JSON files. Downloads are resolved to commits, hash-receipted,
schedule-certified and diff-checked; activation is atomic and all-or-nothing.
Cross-source disagreement, completed-score rewrites, deletion, or sealed
fixture identity/kickoff changes fail closed.

The registry was last verified before the new season and still says that
`football.json` stops at 2025/26. The upstream state has changed:

- [Premier League Football.TXT 2026/27](https://github.com/openfootball/england/blob/master/2026-27/1-premierleague.txt)
  and [JSON](https://github.com/openfootball/football.json/blob/master/2026-27/en.1.json)
  exist;
- [Bundesliga Football.TXT](https://github.com/openfootball/deutschland/blob/master/2026-27/1-bundesliga.txt)
  and [JSON](https://github.com/openfootball/football.json/blob/master/2026-27/de.1.json)
  exist;
- [La Liga Football.TXT](https://github.com/openfootball/espana/blob/master/2026-27/1-liga.txt)
  and [JSON](https://github.com/openfootball/football.json/blob/master/2026-27/es.1.json)
  exist;
- [Serie A Football.TXT](https://github.com/openfootball/italy/blob/master/2026-27/1-seriea.txt)
  and [JSON](https://github.com/openfootball/football.json/blob/master/2026-27/it.1.json)
  exist; and
- [Ligue 1 Football.TXT](https://github.com/openfootball/europe/blob/master/france/2026-27_fr1.txt)
  and [JSON](https://github.com/openfootball/football.json/blob/master/2026-27/fr.1.json)
  exist.

That is upstream availability, not proof that a Golavo generation has fetched,
validated and activated the season. The correct next action is to run the
existing consent-aware approved-source refresh and accept 2026/27 only if all
five schedule certificates pass. Golavo must not bypass that pipeline by
checking new files into an ad hoc pack.

### Exact additional Premier League value available now

OpenFootball can support:

- a 2026/27 matchday list and team-versus-team fixture identity;
- calendar date and an upstream venue-local kickoff clock;
- current score/result after the contributor publishes it; and
- field-level source provenance plus commit and content hashes through Golavo's
  existing refresh receipts.

OpenFootball does not provide a timezone token for the clock. Golavo therefore
keeps day precision, not an invented exact instant. It also provides no venue,
referee, attendance, lineups, player identity, appearances/minutes, goalscorer,
assist, card/event timeline, injury, suspension, shot, pass, possession, rating
or expected-goals field. The files are volunteer-maintained and publish no SLA,
rate guarantee or provider ID contract. Golavo's own canonical identities,
pinned commits and completeness certificate remain the reliability boundary.

The source's [README](https://github.com/openfootball/england#readme) and
[CC0 dedication](https://github.com/openfootball/england/blob/master/LICENSE.md)
permit the existing bundling and redistribution use. GitHub authentication is
not required to read the files; Golavo's existing refresh limits itself to the
allowlisted paths and a daily default interval rather than treating GitHub as a
live match API.

## Proposed current player-analysis integration: Sportmonks only

Sportmonks is the only reviewed provider that combines a useful current player
surface with public standard terms compatible with displaying data in an app.
This approval extends only the existing connector boundary; it does not approve
provider data as Golavo evidence or model input.

### Useful fields

The official [Premier League coverage page](https://www.sportmonks.com/football-api/premier-league-api/)
advertises schedules/results, events, squads/player profiles, lineups,
formations, standings/top scorers, injuries/suspensions, match/team/player
statistics, xG, expected lineups and pressure metrics. The equivalent official
pages exist for [La Liga](https://www.sportmonks.com/football-api/la-liga-api/),
[Bundesliga](https://www.sportmonks.com/football-api/bundesliga-api/),
[Serie A](https://www.sportmonks.com/football-api/serie-a-api/) and
[Ligue 1](https://www.sportmonks.com/football-api/ligue-1-api/).

The [player-statistic type documentation](https://docs.sportmonks.com/football/definitions/types/statistics)
includes minutes, appearances/starts/bench, goals, assists, shots, passes,
pass accuracy, key passes, tackles, interceptions, recoveries, duels/aerials,
dribbles, fouls, cards, saves, clean sheets, errors, big chances, ratings and
expected-goals-related types. Coverage varies by league, season, fixture and
plan. A missing statistic is unavailable, not zero.

The [lineup documentation](https://docs.sportmonks.com/football/tutorials-and-guides/tutorials/lineups-and-formations)
binds lineup records to numeric fixture, team, player and position IDs and
distinguishes predicted from confirmed information. Expected-goals rows bind
fixture, player/team/lineup and metric type IDs to a value; the
[xG documentation](https://docs.sportmonks.com/football/tutorials-and-guides/tutorials/expected/endpoints)
describes subscription-dependent availability. The provider's
[xG FAQ](https://docs.sportmonks.com/v3/beta-documentation/expected-goals/faq)
says available in-match xG is recalculated every couple of minutes; that is not
an SLA and must be observed under the user's actual package.

### Coverage and identity acceptance

The public Premier League marketing page still labels its example/current
season 2025/26 on 2026-08-29. A league name in the catalog is therefore not
enough to claim 2026/27 support. At connection time Golavo must query the user's
permitted leagues/seasons and require:

1. the exact numeric league and 2026/27 season IDs;
2. the fixture's numeric fixture/team/player identities;
3. exact competition/season, canonical home/away team IDs and Golavo calendar
   date matching; the provider's UTC kickoff is displayed as attributed context
   and checked for conflict, not required to equal OpenFootball's timezone-less
   local clock;
4. a field-level coverage probe for lineups, sidelined players, events, player
   statistics and xG under that user's plan; and
5. visible retrieval time, provider update time when present, lineup state and
   missing-field state.

No fuzzy match may become a fact. Duplicate same-date candidates, a provider-ID
remap, ambiguous team, missing season, unexpected competition, or material date
or kickoff conflict leaves the panel unavailable. The initial no-store design
keeps the selected Sportmonks fixture ID only in memory for that request. If a
later reviewed retention design permits storing the mapping, persist the
provider ID with the exact identity tuple and reject any remap rather than
silently replacing it.

### Authentication, price, limits and freshness

Sportmonks uses an API token. It belongs in macOS Keychain and must be sent only
to allowlisted Sportmonks endpoints; never logs, project data, exports or crash
reports. Current [pricing](https://www.sportmonks.com/football-api/plans-pricing/)
advertises Starter at €29/month for five leagues and 2,000 requests per entity
per hour, Growth at €99 for 30 leagues and 2,500, and Pro at €249 for 120 leagues
and 3,000. Expected metrics and older history can require add-ons; the product
must show that cost is the user's responsibility.

The separate [rate-limit documentation](https://docs.sportmonks.com/football/api/rate-limit)
does not currently order all plan names exactly as the pricing page does.
Golavo must not hard-code a marketing-page quota. It should honor HTTP 429 and
the response's remaining/reset/requested-entity metadata. Each requested page
counts. Foreground, match-scoped loading and cancellation are safer than
background polling.

The provider documents
[latest-updated fixtures](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/fixtures/get-latest-updated-fixtures),
[deleted-fixture synchronization](https://docs.sportmonks.com/v3/tutorials-and-guides/guides/how-to-keep-your-database-in-sync)
and a [data-correction process](https://docs.sportmonks.com/v3/api/data-corrections),
but its [terms](https://www.sportmonks.com/terms-of-service/) disclaim guaranteed
accuracy, completeness and availability. Live player stats may change during a
match; xG availability and timing vary by subscription. Display retrieval and
upstream-update time, never claim real-time without observing it, and tolerate
late correction or total absence.

### Rights boundary

The terms contemplate apps, websites and monetized products; permit storing,
transferring and distributing API data; and prohibit directly reselling the
feed. Logos and player/team photos have separate intellectual-property rights,
so Golavo must not request or display them.

Although the standard terms permit storage, the first implementation should
remain the connector's current foreground, in-memory, no-provider-bytes design.
Durable storage would require a separate retention/deletion model, terms-version
receipt, account-disconnect semantics and a reviewed answer for what remains
when a subscription ends. Likewise, raw responses and normalized provider data
must not enter exports.

Terms drift fails closed even for ephemeral display. Record the reviewed terms
URL, review date and content hash (or provider version when published). If a
known material change affects publication, retention, downstream use or media
rights, disable fetching until the new text is reviewed and the registry entry
is updated. A provider recheck date is a maximum review interval, not permission
to continue after a detected change.

Implementation review record (2026-08-30): the reviewed terms HTML at the URL
above had SHA-256
`43901aed7fd5e36e36205e814a064d5851ecb66df8387f0079a586bed6df8aeb`.
`golavo_server.sportmonks.TERMS_ACCEPTANCE_VERSION` embeds that digest, so a
future reviewed text requires a new version and prior consent no longer enables
the connector. The first Player Lens also narrows the proposal below to 41
pinned fixture-player metric IDs with explicit developer names and units.
Unknown IDs, metadata drift and invalid units fail closed; injury detail and xG
remain outside the initial allowlist.

### Minimal `Player Lens` proposal

For a selected match, one attributed panel may show:

- predicted or confirmed starters/bench, with the state explicit;
- position, minutes and provider rating;
- goals, assists, shots/on-target, passes/accuracy/key passes;
- tackles, interceptions, recoveries, duels/aerials and dribbles;
- fouls, cards, saves and clean sheets where positionally relevant;
- provider-reported availability/suspension status, without medical detail; and
- player xG only when the user's plan supplies it, visibly labelled
  **Sportmonks xG**, never Golavo xG.

Every section needs an unavailable state. Do not rank a missing player as zero,
compare players across leagues without minutes/position/coverage controls, or
call a provider rating objective truth.

An injury label is sensitive provider-reported availability, not a verified
medical fact. The first release should exclude diagnosis, body-part, severity,
free-text notes and history. Do not infer a condition, retain an injury history,
send it to AI/telemetry, or expose it outside the selected-match view. If the
source does not support a minimal availability label, omit the group entirely.

## Why the other current APIs are not approved

### football-data.org v4

The official [coverage list](https://www.football-data.org/coverage) includes
the Premier League, Bundesliga, Ligue 1, Serie A and Primera Division in its 12
free competitions. Unique numeric match, competition, season, team and person
IDs support exact matching, but the public documentation does not promise that
IDs are immutable forever. The [match resource](https://docs.football-data.org/general/v4/match.html)
can expose UTC kickoff, status/minute, stage/matchday, attendance/venue, score,
goals, bookings, substitutions and lineups according to plan. Person/squad and
[top-scorer](https://docs.football-data.org/general/v4/scorers.html) resources
add name, birth date, nationality, position, shirt number, appearances/minutes,
goals, assists, penalties and cards. Its paid statistics add-on is mostly
match-level possession, shots, saves, fouls, corners, free kicks, offsides and
cards, not a broad advanced player feed.

The current [pricing page](https://www.football-data.org/pricing) advertises a
free delayed tier at 10 requests/minute, €12/month live scores, €29 deep data,
€49 Standard, €99 Advanced and €199 Pro; odds and statistics start at €15
add-ons. The [API policy](https://docs.football-data.org/general/v4/policies.html)
defines UTC and null/empty semantics but shows a different simplified rate-tier
summary. A client would have to use the subscribed plan/response as truth.

The blocker is not technical. The provider's
[registration terms](https://www.football-data.org/client/register) bind a key
to one application and clause 9.1 says that a customer may no longer reference
obtained fixtures, results, tables, player, squad or top-scorer data after
cancellation; the provider separately requires
[visible attribution](https://www.football-data.org/about). The public standard
terms do not clearly grant Golavo caching, durable normalized storage,
redistribution/export or use of derived outputs. Those omissions and the
post-cancellation restriction are incompatible with a durable, auditable local
record. A zero-retention BYOK view would still be operationally brittle and
offers less player depth than the already-cleared Sportmonks route. Reject until
a written agreement expressly grants in-app display, caching/storage,
retention/deletion, derived-output, redistribution/export and post-cancellation
reference rights for the exact intended roles.

### API-Football

The official [2026 integration guide](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide)
documents numeric fixture/league/season/team/player IDs, league-season coverage
flags, pagination and all top-five leagues. `/fixtures/players` can return
minutes, position, rating, substitute state, shots, goals, assists, passes/key
passes/accuracy, tackles, interceptions, duels, dribbles, fouls, cards and
penalty fields. Other endpoints cover lineups, events, injuries, predictions
and odds. The guide suggests updates of 15–60 seconds for live fixtures/events,
about one minute for fixture/player statistics, 30–60 minutes before kickoff
for lineups, four hours for injuries and one hour for predictions. The service
does not guarantee those frequencies.

Authentication uses an `x-apisports-key` header. Current
[pricing](https://www.api-football.com/pricing) advertises 100 requests/day free,
$19/month for 7,500/day, $29 for 75,000/day and $39 for 150,000/day, with
plan-specific rate headers. The per-season coverage flags are discovery hints,
not proof that every fixture has every field.

The official [terms](https://www.api-football.com/terms) are dispositive: they
say API-Football does not provide a license to use or publish its data in an
application, website or other product and that the customer must obtain
permission from competent rights holders. Direct resale is also prohibited,
and names/logos/images can require further permission. Therefore neither a user
key nor a downstream repository license clears Golavo to display the data.

### StatsBomb Open Data

The first-party repository moved to
[`hudl/open-data`](https://github.com/hudl/open-data). Its
[README](https://github.com/hudl/open-data#readme) describes selected JSON
competitions, matches, events, lineups and some 360 frames for research and
genuine interest. The live
[`competitions.json`](https://github.com/hudl/open-data/blob/master/data/competitions.json)
contains selected historical seasons, not the 2026/27 top-five season. Examples
include Premier League 2015/16 and 2003/04, Bundesliga 2023/24 and 2015/16,
older La Liga/Serie A seasons and Ligue 1 2021/22–2022/23.

The repository's [five-page user agreement](https://github.com/hudl/open-data/blob/master/LICENSE.pdf)
is not an open-source/data license. It forbids editing/distorting, distributing,
reproducing, selling or providing the data to third parties and prohibits
commercial exploitation of both the data and analysis derived from it. Access
is revocable, logo attribution is required, and accuracy/completeness are not
warranted. Static GitHub access has no API key or subscription price, but those
facts do not create product rights. Reject bundling, runtime fetching, display,
forecast use and derived commercial analysis.

## First-party open repositories: research, not current player feeds

### OpenFootball players

The first-party [`openfootball/players`](https://github.com/openfootball/players)
repository is [CC0](https://github.com/openfootball/players/blob/master/LICENSE.md)
and lists player names plus selected position, height, birth date and birthplace
fields by country. It does not document current club or squad membership,
appearances/minutes, match events, performance statistics, systematic top-five
coverage or durable upstream player IDs. Names are not a safe join key.

The data could eventually support a separately reviewed biography reference
pack, but not `Player Lens` and not a model. Defer until a coverage report and
explicit identity map demonstrate that a pin can be reproduced without fuzzy
promotion or misleading current-club claims.

### Pappalardo/Wyscout event data

The first-party [Figshare collection](https://figshare.com/collections/Soccer_match_event_dataset/4415000/5)
is CC BY 4.0 and covers the full 2017/18 top-five seasons plus World Cup 2018 and
Euro 2016. It includes competitions, matches, teams, players, referees/coaches
and detailed time/position/outcome/tagged events. It is valuable for explaining
event analytics and testing historical transformations, but it says nothing
about current form or 2026/27 availability.

Golavo's registered use is already narrower than the source grant: an isolated,
attributed derived research pack, with no redistributed raw events/player
identities, no join into the live index and no “observed xG” label. Keep that
boundary. This report does not approve a new player model or raw-data bundle.

### SkillCorner Open Data

The first-party [`SkillCorner/opendata`](https://github.com/SkillCorner/opendata)
repository is [MIT licensed](https://github.com/SkillCorner/opendata/blob/master/LICENSE).
It covers ten 2024/25 Australian A-League matches with lineup/match metadata,
10fps broadcast tracking, extrapolated player/ball coordinates, dynamic events,
phases of play and selected season-level physical, off-ball-run and passing
aggregates. The README reports approximately 97% player-identity accuracy and
flags extrapolated frames.

It is useful architectural inspiration for typed frames, quality flags and
position-aware aggregates. It is not evidence of current Premier League or
top-five coverage. Keep it in the existing isolated research pack only.

Open code never launders upstream data rights. Community wrappers, scraper
libraries, Kaggle uploads and GitHub mirrors of FBref, Understat, Transfermarkt,
Fantasy Premier League, API-Football or football-data.org are not authoritative
license grants. Their schemas may inspire adapter boundaries only when the
repository's own code license is explicit; no mirrored response or data sample
may be copied into Golavo on that basis.

## Premier League scraping assessment

The official site exposes public [statistics](https://www.premierleague.com/en/stats)
and player/match pages for 2026/27, but the
[website terms](https://www.premierleague.com/en/terms-and-conditions) reserve
copyright and database rights. They limit downloading to personal/private use
and prohibit commercial use, reproduction, reuse, redistribution or creating a
database from site/app content without prior written approval. The terms also
disclaim accuracy, completeness and currency.

The official [`robots.txt`](https://www.premierleague.com/robots.txt) blocks
some query patterns rather than all crawling. That only communicates crawler
preferences. It does not override the terms or grant copyright/database rights.
Undocumented Fantasy Premier League JSON endpoints likewise are not a licensed
product API. Do not scrape HTML, automate pages, call undocumented endpoints or
adopt a GitHub scraper. Reconsider only with written Premier League permission
and a documented API contract.

## Forecast and calibration boundary

| Data | Display | Bundle/store | Forecast training | Calibration / settlement |
|---|---|---|---|---|
| Certified OpenFootball 2026/27 schedule/result | Yes | Yes, through existing CC0 refresh generations | Only completed result rows under the existing accepted feature/provenance contract | One club-result source is insufficient for settlement; schedule rows never calibrate |
| Sportmonks fixture/player facts | BYOK, attributed, selected match only | No bundled data; initially in-memory/no provider bytes | No | No |
| Sportmonks prediction/odds/xG/rating | Separately labelled external context only | No | No | No |
| Pappalardo or SkillCorner research packs | Research UI only | Existing isolated pack rules | No current/live model | No |
| football-data.org, API-Football, StatsBomb, Premier League scrape | No | No | No | No |

A later attempt to train on player data needs a new source decision, not a UI
checkbox. Minimum gates are written model/commercial rights; immutable historical
snapshots; exact player/team/fixture identities; corrections and deletion
semantics; competition-season coverage reports; position/minutes/missingness
controls; provider-version provenance; a pre-kickoff information cutoff that
prevents leakage; time-split backtests; and calibration that remains independent
from the evaluated fixtures. External predictions, odds, provider ratings and
post-match xG should remain excluded even then unless separately justified.

## Implementation acceptance checklist

### OpenFootball 2026/27 refresh

- Use only the registry's exact five country paths and five `football.json`
  paths; resolve each to a full commit SHA.
- Validate CC0 marker, size, parse, schedule certificate, identity/kickoff diffs
  and completed-score changes before atomic activation.
- Confirm that all five competitions are present; record honest
  `absent`/`partial`/`complete` capability rather than infer completeness.
- Preserve day precision for timezone-less local clocks.
- Keep unplayed matches out of training and require an independent cleared
  result source for settlement.

### Sportmonks `Player Lens`

- Opt in per provider; show terms, privacy, cost/plan responsibility, requested
  capabilities, no-store policy, disconnect/delete and last verification date.
- Pin the reviewed terms URL, review date and content hash/version. Disable the
  connector pending review after any known material publication, retention or
  downstream-use change.
- Store the user's secret only in Keychain and use allowlisted HTTPS endpoints.
- Live-probe numeric league/season/fixture/team/player IDs and 2026/27 coverage
  under the user's plan. Match exact competition/season, canonical home/away
  identities and calendar date; treat provider UTC kickoff as attributed
  context/conflict detection because OpenFootball lacks timezone precision.
  Duplicate candidates, date conflicts and remaps fail closed.
- Label predicted versus confirmed lineups, provider/source, captured time,
  upstream update time and every unavailable field.
- Treat absent as unavailable, never zero. Preserve provider metric type IDs and
  units; do not merge unlike rating/xG definitions.
- Treat injury data only as minimal provider-reported availability. Exclude
  diagnosis, medical detail, history, inference, AI and telemetry.
- Use foreground match-scoped fetches, pagination, response rate metadata,
  backoff and 429 handling; no hidden polling or background daemon.
- Request no logos, photos, bookmaker links, affiliate tracking, staking advice
  or bet placement.
- Persist no raw or normalized provider bytes; export none; route nothing into
  models, seals, verdicts, settlement, scoring, calibration or AI evidence.
- On disconnect, cancel pending requests, delete the Keychain token, clear all
  in-memory responses and provider-specific WebView/network caches, and verify
  that no token or payload is persisted in recorded URLs, logs, caches, crash
  reports or telemetry. If the API transport requires a query token, redact it
  before any observation or storage.

Any future reconsideration of football-data.org, API-Football or another
commercial source requires its own reviewed terms URL plus content hash/version,
review date and recheck date before a token is accepted or a request is sent.
An acceptance checkbox cannot supply rights that the provider's terms omit.

## Sources reviewed

Primary evidence: Golavo's current
[source registry](../../data/sources/registry.json),
[ADR-0004](../adr/0004-approved-source-refresh.md) and
[ADR-0006](../adr/0006-source-backed-match-context.md); the first-party source,
documentation, license, pricing and terms links inline above. No dataset was
downloaded or added. The StatsBomb license PDF was visually inspected as well
as text-extracted. No community mirror, Kaggle upload or scraped sample was used
as a rights grant.
