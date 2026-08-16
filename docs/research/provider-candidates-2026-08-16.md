# Opt-in football provider candidates

**Verified:** 2026-08-16. **Method:** the current
[public-apis sports catalog](https://github.com/public-apis/public-apis#sports--fitness)
was used only for discovery. Every product, price, field, coverage and rights
claim below was checked against the provider's own documentation, pricing and
terms. The catalog's MIT license covers the catalog, not any listed provider's
data.

## Decision

| Provider | Decision | Permitted Golavo role |
|---|---|---|
| **Sportmonks Football v3** | **Select** | Display context; separately labelled external odds/predictions; candidate result-confirmation leg after an independence/accuracy trial |
| **TheSportsDB v2, paid** | **Defer — below the current quality bar** | Possible lower-trust display fallback only after stable-ID, correction and coverage evidence improves |
| **Odds-API.io** | **Hold for written permission** | Odds-only overlay after the provider confirms that end-user in-app display is not prohibited redistribution |
| API-Football | Reject until publication rights are cleared | None in a shipped app |
| football-data.org | Reject as a durable local-first connector | None; cancellation terms conflict with retained local records |
| TheRundown | Reject under standard terms | None without a supplemental agreement |
| PlayerElo | Reject for now | None; public schema and commercial-rights contract are insufficient |
| Bet Better | Reject for now | Experimental link-out at most; no production connector |
| SportScore | Reject despite attractive API claims | Its developer offer and general terms materially conflict |

**No provider is approved as a sole grading authority.** Sportmonks is the only
clear production starting point. TheSportsDB is inexpensive but remains below
the current quality bar. A provider-specific acceptance step is necessary, but
it does not grant rights that the provider's contract withholds.

## Production candidate and deferred fallback

### 1. Sportmonks Football v3 — strongest overall

**Documented facts.** Sportmonks exposes a mature REST/JSON v3 API with token
authentication, numeric fixture/team/player/league/bookmaker/market IDs, a broad
[endpoint surface](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints),
and a current changelog. The fixture contract exposes `id`, `league_id`,
`season_id`, `state_id`, `venue_id`, `name`, `starting_at`,
`starting_at_timestamp`, `result_info`, `placeholder` and `has_odds`. Odds rows
carry `fixture_id`, `market_id`, `bookmaker_id`, `label`, `value`, `name` and
`market_description`; predictions bind `fixture_id` and `type_id` to a
type-dependent `predictions` value. Useful fixture data includes kickoff and match state,
scores, events, formations, confirmed or predicted lineups, injuries and
suspensions, team/player statistics, xG and other expected metrics. Its odds
surface includes pre-match, in-play and historical feeds; its prediction surface
includes fixture probabilities. The provider documents a
[latest-fixture update feed](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/fixtures/get-latest-updated-fixtures),
[database synchronization including deleted fixtures](https://docs.sportmonks.com/v3/tutorials-and-guides/guides/how-to-keep-your-database-in-sync),
a [data-correction process](https://docs.sportmonks.com/v3/api/data-corrections),
and [timezone behavior](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/timezone-parameters-on-different-endpoints).
Lineup metadata distinguishes predicted from confirmed teams, and xG availability
depends on plan and processing latency
([lineups](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/lineups-and-formations),
[xG](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/expected/endpoints)).

Current [pricing](https://www.sportmonks.com/football-api/plans-pricing/) starts
at €29/month for five selected leagues and 2,000 calls per entity per hour;
Growth starts at €99/month for 30 leagues and Pro at €249/month for 120. A
14-day paid-plan trial is offered. The Odds & Predictions bundle currently
starts at €15/month and advertises pre-match/in-play odds, 50+ bookmakers and
150+ markets. Historical access older than three seasons is a separate add-on
below Enterprise.

Most importantly, Sportmonks' [terms](https://www.sportmonks.com/terms-of-service/)
expressly contemplate applications, websites and monetized products; permit
distribution, transfer and storage of API data; and prohibit direct resale of
the feed. Logos and profile photos require separate rights and therefore should
not be requested or displayed by Golavo. Accounts may not be shared, and pricing
is domain-scoped. Odds availability and data accuracy are not guaranteed.

**Assessment / inference.** A user-owned Sportmonks token is feasible in the
desktop app and the published data rights fit local storage better than every
other commercial candidate reviewed. Select it for:

- fixtures, lineups, injuries, suspensions, match events, statistics and xG as
  attributed provider context;
- a separately labelled **Sportmonks external prediction** panel;
- a separately labelled bookmaker-odds panel, with bookmaker, market, selection,
  captured time and upstream update time visible; and
- one result-confirmation leg, but only after Golavo validates competition
  coverage, stable identity mapping, corrections and independence from the
  second source.

Sportmonks probabilities, predictions, value-bet outputs, xG and odds must never
be blended into, reweight or overwrite Golavo's engine probabilities or sealed
forecast. They are an external opinion beside the immutable forecast.

### 2. TheSportsDB v2 — defer below the high-quality bar

**Documented facts.** TheSportsDB offers a long-running v1 API and a newer v2
API. Its own [documentation](https://www.thesportsdb.com/docs_api_guide) calls v1
messy and says only v2 will be developed going forward; v2 uses header-based
authentication and standard HTTP status codes. Numeric event/team/player IDs
(`idEvent`, `idHomeTeam`, `idAwayTeam`, `idPlayer`) support event, result,
lineup, timeline, statistics, schedule, standings and
livescore lookups. It documents 30 requests/minute on free, 100 on Premium and
120 on Business; current [monthly pricing](https://www.thesportsdb.com/docs_pricing.php)
is $9 for a single developer and $20 for a small business. Premium includes v2
and two-minute soccer livescores. The service is crowd-sourced and does not
document an injury feed, a correction SLA, a stable-ID guarantee or sufficiently
precise competition-by-field coverage.

The [terms](https://www.thesportsdb.com/docs_terms_of_use.php) allow API content
to be copied and modified through official endpoints, prohibit direct API
resale, require a paid subscription for app-store publication, require source
credit for paid use, and preserve third-party artwork/trademark restrictions.
Golavo should omit all provider artwork and logos.

**Assessment / inference.** Do not integrate it in the current high-quality-only
rollout. Paid v2 could later be a visibly lower-trust, user-selected display
connector for fixtures, results, lineups, timelines and statistics, but only
after a fixture-level quality trial establishes stable identity, coverage and
correction behavior. Do not use the public v1 key in a production app.
Crowd-sourced provenance and undocumented correction/independence semantics make
it unsuitable for automatic grading. Missing fields must display as unavailable,
not zero. No TheSportsDB fact may replace a core or Sportmonks fact silently.

## Technically strong but not cleared

### Odds-API.io — good odds transport, ambiguous display right

Odds-API.io's current [v3 documentation](https://docs.odds-api.io/) is strong:
REST and WebSocket access, numeric event/participant IDs, RFC 3339 UTC kickoffs,
pending/live/settled status, per-market `updatedAt`, bookmaker and market maps,
and exact event fields including `id`, `home`, `away`, `homeId`, `awayId`,
`date`, `status`, `sport`, `league` and `scores`. Odds responses add
`bookmakerIds`, `bookmakers` and `urls`. The API also exposes historical closing
odds, odds movements, sequence replay and explicit
`resync_required` recovery. The provider advertises 265+ bookmakers, 34 sports
and 12,000+ leagues. The free tier is for development/testing and currently
allows 100 requests/hour and 500/day with two books; paid production access
starts at £49/month, and paid REST plans document 5,000 requests/hour
([pricing](https://odds-api.io/),
[authentication/rates](https://docs.odds-api.io/authentication)).

Its [terms](https://odds-api.io/terms) prohibit resale, redistribution,
sublicensing and competing services without written consent. Provider guides
encourage local historical storage, but the contract does not clearly say that
displaying normalized odds to Golavo users is permitted rather than
redistribution. **Hold implementation until Odds-API.io confirms in writing that
a local desktop app may display and cache its data.** If cleared, use a
user-owned paid key for an odds-only overlay; never bundle a Golavo-wide key or
republish raw responses.

### API-Football — excellent API, missing publication license

API-Football is technically attractive. Its official current guide documents
1,200+ competitions, numeric resource IDs, fixtures and results, status changes,
events, lineups, injuries/sidelined history, detailed team/player statistics,
pre-match/in-play odds and its own predictions. The prediction response includes
`winner`, `win_or_draw`, `under_over`, home/away `goals`, `advice`,
home/draw/away `percent` and `comparison`; odds include bookmaker, bet and value
records. Fixtures expose `fixture.id`, `fixture.timestamp`, `fixture.date`,
`fixture.status`, `goals.home` and `goals.away`; lineups expose formation,
starting XI, substitutes and coach. Fixture timestamps are UTC Unix values and ISO
8601 dates include offsets. Current documented update guidance is roughly 15
seconds for live fixtures/events, one minute for live statistics, 30–60 minutes
before kickoff for many lineups, four hours for injuries, one hour for
predictions and three hours for pre-match odds; only seven days of pre-match odds
history are retrievable
([current integration guide](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide)).
The [free plan](https://www.api-football.com/pricing) provides all endpoints but
only 100 requests/day and limited seasons; paid daily quotas currently start at
$19/month for 7,500 requests/day.

The blocker is contractual. The [terms](https://www.api-football.com/terms)
permit creating applications and prohibit direct data resale, but explicitly
say API-Football does **not** provide a license to use and publish the data in an
application, website or other product; users must obtain permission from the
competent rights holders. Logos/images also require separate authorization.
Availability, correctness and support response are not backed by an SLA.
Therefore a Golavo acceptance checkbox is not enough. Reject until written
publication/display rights for this exact local-app use are obtained.

### football-data.org — mature but hostile to durable local records

football-data.org v4 has clear resource docs, numeric unique IDs, fixtures,
scores, match status, UTC defaults, competitions, teams, standings and scorers;
paid tiers add lineups, substitutions, goals, cards, squads, trend/form data,
odds and match statistics. Its [API policy](https://docs.football-data.org/general/v4/policies.html)
defines null/empty semantics, UTC date defaults and rate limits. Current
[pricing](https://www.football-data.org/pricing) offers 12 delayed competitions
and 10 calls/minute free; live scores start at €12/month, deep data at €29,
Standard at €49, and odds/statistics are paid add-ons.

Its [terms](https://www.football-data.org/about) bind a key to one application,
require visible attribution and independent rights for graphics, and prohibit
referencing any obtained football data after subscription cancellation. That
last restriction is incompatible with Golavo's durable local provenance and
settlement artifacts. Reject as a persistent connector unless a separate
agreement grants post-cancellation retention/reference rights.

### TheRundown — strong schema, standard contract says no

TheRundown v2 is technically production-grade: canonical event/team IDs, UTC
times, scores and status, normalized markets and lines, source-specific update
timestamps, delta/history/open/close/best-line APIs and broad major-league soccer
coverage. Its public model includes `event_id`, `sport_id`, `event_date`,
`score.event_status`, `score.updated_at`, `markets[].market_id`,
`markets[].period_id`, participant lines/prices and per-source `updated_at`.
Current [pricing](https://therundown.io/pricing/api) ranges from a
delayed free tier to $49/month Starter, $149 Pro and $399 Ultra.

The current [standard terms](https://therundown.io/terms-and-privacy) allow only
internal personal/business use absent a supplemental agreement; prohibit public
display/redistribution, commercial exploitation, statistical-model use and
source-obscuring commingling; limit storage to real-time need or 24 hours; and
require deletion after termination. Reject unless a custom agreement expressly
permits Golavo display, retention and intended computation.

## Not high-quality enough yet

- **PlayerElo.** The [public API page](https://playerelo.football/api-access)
  offers player/team/coach Elo, match probabilities, scoreline odds and value
  bets across a claimed 176 competitions, with Bearer auth and a small free tier.
  It does not publish a complete response schema/OpenAPI contract, stable-ID or
  correction policy, retention/publication terms, or an unambiguous commercial
  license by tier. Freshness statements are inconsistent. Reconsider only after
  receiving those artifacts and running a fixture-level quality audit.
- **Bet Better.** Its [open model API](https://betbetter.world/api/) is unusually
  clear about CC BY 4.0 reuse and returns UTC kickoffs, model probability, fair
  odds, confidence and verdict without a key. It intentionally excludes raw
  bookmaker prices. However, picks have no fixture/team/selection IDs, schema
  version or correction/retraction mechanism; string-and-time matching cannot
  meet Golavo's production identity bar. Keep it as a labelled external link,
  not a connector.
- **SportScore.** The provider's [developer page](https://sportscore.com/developers/)
  advertises keyless JSON, about 10,000 requests/day, lineups/stats/results and a
  visible dofollow attribution requirement. Its current
  [general terms](https://sportscore.com/terms/) simultaneously restrict the
  site to personal, non-commercial use; prohibit database extraction/public
  display without consent; and prohibit automated requests. Do not integrate
  until a signed API-specific license resolves that conflict.

## Golavo connector contract

These are implementation gates, not optional polish:

1. **Consent and credentials.** Keep current Golavo as the default. Every
   provider gets its own opt-in, terms/privacy links, terms version/review date,
   requested capabilities, data sent, storage policy, cost/rate-limit disclosure
   and Disconnect/Delete action. Acknowledgment is provider-specific. Keyed
   providers require the user's own account/key; store secrets in macOS Keychain,
   never project data, exports, logs or crash reports.
2. **Strict roles.** Persist `display`, `grading_leg`, `external_prediction` and
   `external_odds` as separate capabilities. Only the last two may show provider
   probabilities/odds, always labelled with provider and capture time. No
   external probability, advice, value-bet flag, xG or odds-derived implied
   probability enters Golavo model fitting, council aggregation, sealing,
   calibration or deterministic verdicts.
3. **Exact identity and provenance.** Allowlist provider hosts and endpoints.
   Map reviewed stable provider IDs to Golavo fixture/team/competition IDs;
   never fuzzy-promote an unmatched response. Record provider and upstream IDs,
   endpoint, terms/plan version, retrieved-at time, upstream update time,
   bookmaker/market/selection, raw-response SHA-256 and correction/status state.
   Store raw bytes only where retention/storage rights have been confirmed.
4. **Grading fails closed.** A result provider may be one evidence leg only.
   Settle a club forecast only after two independently cleared sources identify
   the exact fixture and agree on the final score after the existing grace
   period. Disagreement, correction-in-progress, ambiguous identity or unknown
   source independence leaves the forecast pending. External predictions and
   odds are never grading evidence.
5. **Offline and failure behavior.** Never fall through to a provider the user
   did not enable. On 401/403, disable refresh and prompt for credential or plan
   repair; on 429, stop the capability cascade and further requests in the active
   panel rather than retrying automatically; on timeout/5xx,
   keep the last verified generation only if retention permits it. Clearly mark
   stale/provider-unavailable states. Empty data is not zero and not a success.
   Quarantine malformed, duplicate or conflicting rows. Disconnect disables all
   access and deletes provider data where the contract or user choice requires
   it.
6. **Pre-release evidence.** Run per-competition coverage and identity audits,
   record missing-field/null rates, compare kickoff/status/final-score corrections
   over multiple matchdays, test quota exhaustion and offline launch, and obtain
   written confirmation for every ambiguous publication/retention clause. Review
   gambling-content age, jurisdiction and app-store obligations separately.

## Recommended rollout order

1. Sportmonks display context (no artwork), then external predictions and odds
   as separately enabled sub-capabilities.
2. Defer TheSportsDB until a stable-ID, correction and field-coverage audit
   clears the current quality gap.
3. A result-confirmation trial that records disagreements and correction lag but
   does not grade forecasts. Promote a source to `grading_leg` only after the
   two-source independence and accuracy gate passes.
4. Revisit Odds-API.io only after written display/caching clearance. Do not build
   the other adapters under their current public contracts.
