# Live-match, completed-match, and transfer intelligence expansion

**Verified:** 2026-08-30. **Scope:** live and completed football match facts,
player availability and form, current transfers and transfer-payment
explanations, plus open-source implementation patterns. This is a product,
provenance, and provider-contract assessment, not legal or gambling advice.

## Decision

1. **Extend the existing Sportmonks connector, but keep it BYOK, foreground,
   attributed, and isolated.** It is the only already-reviewed provider with a
   practical standard contract and one API surface spanning fixtures, scores,
   events, lineups, sidelined players, match/player statistics, and transfers.
   Sportmonks permits applications and permits storage/transfer of API data, but
   forbids direct feed resale and does not guarantee completeness, accuracy, or
   availability. Golavo's current no-store and no-model-use restrictions should
   remain until separate retention and model-rights decisions are approved.
   ([Sportmonks terms](https://www.sportmonks.com/terms-of-service/),
   [current Golavo source decision](../../data/sources/registry.json),
   [current player-data assessment](current-premier-league-player-data-2026-08.md))
2. **Ship no new live-player or transfer claims without credentials.** The
   credential-free core can keep using certified CC0 OpenFootball schedules and
   results. The consented OpenLigaDB ODbL overlay can show its narrow German
   match/result/goal context. Neither source provides a dependable current feed
   for corners, cards, lineups, injuries/suspensions, player match form, or
   transfers. Those capabilities must render as unavailable, not inferred.
   ([OpenFootball](https://openfootball.github.io/),
   [OpenLigaDB API and data model](https://github.com/OpenLigaDB/OpenLigaDB-Samples),
   [Golavo OpenLigaDB ADR](../adr/0005-openligadb-odbl-overlay.md))
3. **Do not promote proprietary provider facts into forecasts yet.** A paid API
   subscription is not evidence of permission to train a model, redistribute a
   derived database, or retain a reproducible training corpus after the
   subscription ends. Before corners, cards, player-scorer, lineup, or
   availability facts can train a Golavo model, obtain written commercial and
   model/derived-output rights and pass a separate time-split, correction, and
   provenance review. The local AI remains an explainer of sealed deterministic
   outputs; it cannot verify, replace, or override them.
   ([Golavo AI contract](../../docs-site/src/content/docs/ai/providers.md),
   [match-analysis contract](../contracts/match_analysis.schema.json))
4. **Do not scrape Transfermarkt, league sites, or undocumented endpoints.**
   Transfermarkt expressly prohibits bots, spiders, screen scraping, other
   automated copying, and AI/model use of its digital content. An open-source
   scraper's code license cannot grant rights to the data it retrieves.
   ([Transfermarkt terms, section 11.1](https://www.transfermarkt.com/intern/anb),
   [Golavo source policy](free-open-data-sources.md))

This decision clears a provider-backed **match intelligence** and **transfer
ledger** design. It does not clear bet placement, staking guidance, an assertion
that any outcome is a “best bet,” or jurisdiction/app-store gambling obligations.
Those require their own product and legal review even when the underlying sports
data is licensed.

## What each requested feature actually needs

| Product claim | Required source/model | Safe source now | Shipping boundary |
|---|---|---|---|
| Final score and completed result | Stable fixture identity, terminal state, score, correction state | Certified OpenFootball core; OpenLigaDB display overlay; Sportmonks BYOK context | Core result activation still follows Golavo's existing source certificates. One provider cannot silently settle or rewrite a sealed forecast. |
| Goal timeline and scorer | Typed event IDs, team/player IDs, minute and event qualifiers | Sportmonks BYOK; narrower OpenLigaDB goal rows for supported German leagues | Provider context only. OpenLigaDB remains ODbL-isolated and may not enter the CC0 model core. |
| Yellow/red cards and corners | Match event/statistic types plus completeness flags | Sportmonks BYOK | Display only. Missing is unavailable, never zero. A forecast requires separately licensed historical snapshots and a new model. |
| Lineups and formations | Fixture/team/player IDs and lineup state | Sportmonks BYOK | Preserve predicted versus confirmed state; never present an expected lineup as official. |
| Player availability | Sidelined/injury/suspension state and provider update time | Sportmonks BYOK | Minimal availability wording only; do not infer diagnoses, recovery dates, or fitness. |
| Player “form” | Minutes and match-scoped player-stat histories with exact competition/season identity | Sportmonks BYOK | Descriptive provider context only. Do not silently mix rating definitions, seasons, competitions, or missing rows. |
| Match winner, exact score, BTTS, clean sheet | Existing leak-safe deterministic models and score matrix | Golavo core | Already inside the deterministic authority boundary. An over/under marginal can be derived only by the same engine from its full score matrix, not by AI prose. |
| Player to score, card count, corner count | Outcome-specific models trained on licensed, point-in-time event history | None approved for model use | Do not ship a numeric prediction until data rights, coverage, leakage, calibration, and abstention gates pass. |
| Current transfer in/out | Transfer ID, player/team IDs, type, date, completion state | Sportmonks BYOK | Provider-attributed ledger entry; rumours remain a separate non-factual lane. |
| Fee and payment breakdown | Primary club/issuer disclosure plus regulatory training-reward source | No universal feed | Show only disclosed components. Unknown installments, add-ons, sell-ons, agent fees, and training rewards remain explicitly unknown. |

Sportmonks documents match events, statistics, lineups, and sidelined players as
fixture includes; its statistic dictionary includes corners as type `34`, and
its event surface covers goals, cards, and substitutions. Coverage still varies
by league, season, fixture, and subscription, so a catalog entry is not proof of
field completeness.
([fixture endpoints and includes](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/fixtures),
[statistic types](https://docs.sportmonks.com/v3/definitions/types/statistics),
[lineups and sidelined players](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/lineups-and-formations),
[live events](https://docs.sportmonks.com/v3/world-cup-2026/live-matches-livescores-and-events))

## Provider due diligence

### Recommended provider

#### Sportmonks Football API v3 — approve only as an extension of the existing BYOK lane

**Field fit.** The v3 fixtures/livescores surfaces can include scores,
participants, events, lineups, state, periods, statistics, formations,
sidelined players, referees, xG, and other plan-dependent entities. The
`/livescores/latest` endpoint reports fixtures changed in the preceding ten
seconds; `/fixtures/latest` covers latest fixture changes and can include
deleted rows. Transfers have first-party endpoints for all, latest, date range,
team, player, and ID lookups.
([live-match guide](https://docs.sportmonks.com/v3/world-cup-2026/live-matches-livescores-and-events),
[latest-updated fixtures](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/fixtures/get-latest-updated-fixtures),
[transfer endpoints](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/transfers))

**Access, cost, and quota.** A user token is required. Current public monthly
starting prices are €29 for five leagues, €99 for 30, and €249 for 120, with
advertised per-entity hourly limits of 2,000, 2,500, and 3,000 respectively.
The detailed rate-limit page and pricing page currently disagree on the Growth
and Pro labels, so Golavo must treat the authenticated response's `rate_limit`
metadata and the user's actual plan as authoritative rather than hard-code a
tier allowance. A `429` stops that capability until reset; it must not trigger a
hidden request cascade.
([current pricing](https://www.sportmonks.com/football-api/),
[rate-limit contract](https://docs.sportmonks.com/v3/api/rate-limit))

**Rights and reliability.** The terms contemplate apps, websites, and games;
permit distribution, transfer, and storage of API data; prohibit direct resale;
and reserve logo/photo rights. They also disclaim completeness, accuracy, and
availability. The provider documents a correction process, but no correction
SLA is promised. Retain Golavo's no-artwork rule and fail closed when a field,
identity, or correction state is unclear.
([terms](https://www.sportmonks.com/terms-of-service/),
[data corrections](https://docs.sportmonks.com/v3/api/data-corrections))

**Model-rights conclusion.** The standard terms support the already-approved
display connector, but the reviewed public contract does not expressly define
Golavo's intended training corpus, derived model, reproducible snapshot, and
post-cancellation rights. Do not use Sportmonks match facts, predictions, odds,
xG, ratings, or value-bet outputs in model fitting, calibration, seals,
settlement, or AI evidence without a written addendum. Sportmonks' own
probability API covers winner, correct score, over/under, and BTTS and requires
a Predictions add-on; if displayed at all, it is an external provider opinion,
not a verification of Golavo's model.
([Sportmonks probabilities](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/odds-and-predictions/predictions/probabilities),
[Golavo provider contract](../../data/sources/registry.json))

### Credential-free sources

#### OpenFootball — keep as certified schedule/result core

OpenFootball describes its Football.TXT/JSON repositories as free public-domain
football data, and the country repositories used by Golavo carry CC0
dedications. The source supplies current 2026/27 top-five schedules and later
score updates, but it publishes no football-specific freshness, correction, or
availability SLA and no systematic current event/player/transfer contract.
Golavo may continue to pin commits, hash bytes, certify schedules, and activate
all-or-nothing generations; it must not reinterpret this static source as a live
event API.
([OpenFootball project](https://openfootball.github.io/),
[England repository CC0 dedication](https://github.com/openfootball/england/blob/master/LICENSE.md),
[current-season assessment](current-premier-league-player-data-2026-08.md))

#### OpenLigaDB — keep as the existing optional ODbL overlay

OpenLigaDB is a keyless community-maintained API. Its official documentation
exposes match IDs, dates, teams, result arrays, goals, tables, and a last-change
check; authenticated community members may edit results, and duplicate or
partially maintained competitions can exist. The API data is ODbL, while the
official code-sample repository is Apache-2.0. Golavo's accepted decision is
therefore correct: retain a consented, separately stored, attributed,
display-only overlay with no fuzzy promotion, model use, sealing, settlement,
or export.
([official API samples and data model](https://github.com/OpenLigaDB/OpenLigaDB-Samples),
[keyless access and ODbL statement](https://beta.openligadb.de/),
[Golavo ADR-0005](../adr/0005-openligadb-odbl-overlay.md))

The documented OpenLigaDB schema has goals and results but no stable contract
for corners, cards, lineups, player availability, or transfers. It cannot fill
the requested rich-match and transfer gaps.
([OpenLigaDB Swagger](https://api.openligadb.de/index.html),
[official sample documentation](https://github.com/OpenLigaDB/OpenLigaDB-Samples))

### Alternatives not approved

| Provider | Technical fit | Terms, stability, and access | Decision |
|---|---|---|---|
| **TheSportsDB v2** | Livescores, schedules, event lookup, and broad team/player surfaces; thinner and less explicit than Sportmonks for availability, event completeness, and correction history | Paid v2 uses header auth. Official docs currently advertise $9/month Premium, 100 requests/minute, and roughly two-minute soccer livescores. Terms allow official-API content in paid apps with attribution and prohibit website scraping, but the database is crowdsourced and publishes no stable-ID, field-coverage, or correction SLA. ([docs](https://www.thesportsdb.com/documentation), [terms](https://www.thesportsdb.com/docs_terms_of_use.php)) | **Defer.** Lower-cost display fallback only after a competition-by-field quality trial. No model or settlement role. |
| **football-data.org v4** | Paid tiers add lineups, substitutions, goals, cards, squads; a paid statistics add-on advertises corners, fouls, shots, possession, saves, and cards | API key and visible attribution. Free is 10 calls/minute; current paid limits and features vary by tier. Terms prohibit referencing obtained football data after cancellation, conflicting with durable local provenance. ([pricing](https://www.football-data.org/pricing), [policy](https://docs.football-data.org/general/v4/policies.html), [terms](https://www.football-data.org/client/register)) | **Reject under standard terms.** Reconsider only with a custom retention/reference agreement. |
| **API-Football** | Strong live fixture, event, lineup, injury/sidelined, player-stat, transfer, prediction, and odds coverage, controlled per league-season by coverage flags | Key required; quotas depend on plan. The provider expressly says it does not grant the right to use/publish its data in an app or product and directs customers to obtain rights from competent authorities; data/freshness are not guaranteed. ([integration guide](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide), [terms](https://www.api-football.com/terms)) | **Reject.** Technical quality cannot cure missing publication rights. |
| **StatsBomb Open Data** | Rich event, lineup, and selected 360 files, but selected historical competitions rather than a complete current-season feed | Keyless static GitHub access. The first-party user agreement is revocable and prohibits distribution/reproduction and commercial exploitation of the data or derived analysis. ([repository](https://github.com/statsbomb/open-data), [user agreement](https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf)) | **Reject for shipped data and model use.** It is not an open-data license despite the repository name. |
| **Transfermarkt** | Current transfer, fee, market-value, and squad pages are attractive but not a documented product API | The official terms prohibit bots, spiders, screen scraping, automated copying, and AI/model use of digital content. ([terms](https://www.transfermarkt.com/intern/anb)) | **Reject scraping and scraper-derived mirrors.** Seek a written commercial feed if Transfermarkt data is essential. |

## Completed-match refresh contract

### Credential-free path

- Keep the existing consent-aware OpenFootball refresh as the only
  credential-free route that may update core club schedules/results. It resolves
  an upstream commit, hashes the source, validates the schedule and identity
  diff, and atomically activates only a certified generation.
  ([ADR-0004](../adr/0004-approved-source-refresh.md))
- Keep OpenLigaDB refresh visible, user-consented, and overlay-only. Do not add a
  launch agent, closed-app worker, or invisible daemon. Existing bounded
  handling for `429`, `503`, cancellation, and the shared request deadline
  remains the correct failure behavior.
  ([ADR-0005](../adr/0005-openligadb-odbl-overlay.md))
- Neither source can populate a rich completed-match player/stat record. The UI
  should say **Detailed match data unavailable without a connected provider**.

### Sportmonks BYOK path

1. **Capability probe.** On connection and before each new competition/season,
   require the exact league, season, fixture, home/away team, and distinct
   numeric provider IDs. Probe the user's actual entitlement to events,
   statistics, lineups, sidelined data, players, and transfers. Duplicate or
   ambiguous matches fail closed.
2. **Selected live match only.** While the user has a match cockpit open and the
   provider state is live, use the livescore endpoint. The ten-second latest
   window is a change trigger, not a durable log: network jitter or a closed app
   can miss it. Respect response rate metadata, back off on empty windows, and
   stop when the user leaves, disables the provider, or closes Golavo.
   ([latest livescores behavior](https://docs.sportmonks.com/v3/world-cup-2026/live-matches-livescores-and-events),
   [rate limits](https://docs.sportmonks.com/v3/api/rate-limit))
3. **Terminal reconciliation.** When the fixture enters a terminal state, fetch
   that exact fixture by ID with scores, state, participants, events,
   statistics, lineups, formations, and sidelined data. Never infer finality
   from a non-empty score. Preserve provider `type_id` values and the distinction
   between absent data and numeric zero.
4. **Correction reconciliation.** A later user-triggered completed-match refresh
   re-fetches the exact fixture and compares provider update/deletion state.
   Corrections create a new attributed display revision; they never mutate the
   already-sealed forecast. Provider-deleted, remapped, or conflicting fixtures
   become unavailable and retain an audit event rather than silently
   disappearing.
   ([latest-updated/deleted fixture behavior](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/fixtures/get-latest-updated-fixtures),
   [correction process](https://docs.sportmonks.com/v3/api/data-corrections))
5. **Retention remains a separate gate.** The first version may keep the current
   in-memory/no-provider-bytes rule. A durable completed-match archive needs a
   new license-isolated store, provider terms receipt, raw-response hash,
   endpoint/plan/schema metadata, revision chain, retention duration, and
   Disconnect/Delete behavior. Nothing enters a source pack, export, training
   row, calibration row, settlement record, or AI evidence by implication.

The latest-updated endpoint cannot be the sole synchronization mechanism: its
window is fixed at ten seconds. A foreground app will inevitably be closed for
longer intervals. Exact fixture-by-ID reconciliation after completion and on
later explicit refresh is therefore the fail-closed design inference from the
provider's documented pull model and update window.

## Transfer ledger and fee explanation

### What Sportmonks can establish

Sportmonks transfer rows carry a transfer ID, player ID, type ID, from/to team
IDs, position IDs, date, completion flag, completion timestamp, and an `amount`
string that may be null. The latest endpoint is paginated and returns only
transfers inside the user's subscription. It does not document structured
currency, guaranteed versus contingent consideration, installments, loan fee,
option/obligation conditions, sell-on clauses, agent/intermediary fees, or FIFA
training rewards.
([latest-transfer schema](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/transfers/get-latest-transfers),
[transfer endpoint family](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/transfers))

Use Sportmonks as the current-transfer index, not as proof of a “full payment
breakdown.” Preserve its amount exactly as a provider claim. Do not parse a free
text amount into a guaranteed numeric fee unless the provider documents that
representation and currency.

Sportmonks also exposes a separate transfer-rumour family and explicitly warns
that those rows are rumours rather than confirmed transfers. Do not merge that
lane into completed transfers, team rosters, form analysis, or model evidence.
([transfer-rumour contract](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/transfer-rumours))

### How a real payment breakdown should work

A transfer page should have two visibly different evidence layers:

- **Transfer record:** provider ID, player, from/to teams, type, transfer date,
  completion state, provider amount string, retrieved time, and provider source.
- **Primary financial disclosure:** acquiring/selling club or issuer, canonical
  document URL, publication date, captured quote and hash, currency, loan fee,
  guaranteed consideration, payment period/installment count, option or
  obligation conditions, maximum contingent bonuses, additional costs,
  disclosed solidarity/training components, and explicit unknown fields.

Public club disclosures demonstrate why one total is misleading. Juventus'
official 2025 Lloyd Kelly filing separated a loan consideration, additional
costs, a conditional obligation for definitive acquisition, a three-financial-
year payment period, and further performance-linked consideration. That is a
useful schema example, not a reusable data license or proof that other clubs
disclose the same fields.
([Juventus primary filing](https://www.juventus.com/images/image/private/fl_attachment/dev/icwejgxyzoeqms3z8oz6.pdf))

The FIFA Clearing House is authoritative only for training rewards, not for the
entire negotiated transfer price. FIFA's electronic player passport process
produces allocation statements for training clubs, and its FAQ says a transfer
paid in multiple installments generates an allocation statement for each
installment. Those records explain solidarity/training-reward mechanics; they
do not create a public API for every club-to-club installment, add-on, sell-on,
or agent payment.
([FIFA EPP process](https://inside.fifa.com/en/transfer-system/clearing-house/epp-process),
[FIFA Clearing House FAQ](https://inside.fifa.com/en/subuniverse-clearing-house/clearing-house-faqs),
[FIFA payment process](https://inside.fifa.com/subuniverse-clearing-house/payment-process),
[current FIFA legal documents](https://inside.fifa.com/legal/documents))

### Transfer-source acquisition rules

- Do not create a general-purpose club-site scraper. An official club/issuer
  document can enter only through a reviewed source-specific host/path/content
  policy, deterministic parser, exact quote, and correction proposal. The
  existing research workflow is foreground-only and treats every extraction as
  an untrusted candidate.
  ([ADR-0009](../adr/0009-evidence-bound-research-extraction.md))
- Link to a primary club announcement when no parser/policy exists. Do not copy
  an unsourced media estimate into a factual fee field.
- Keep `undisclosed`, `not provided`, `provider estimate`, and `primary
  disclosure` as different states. Unknown is not zero.
- Never silently sum guaranteed fees, maximum add-ons, additional costs, and
  training rewards. Show a “maximum disclosed consideration” only when the
  primary source gives compatible components and the UI explains the
  assumptions.
- Treat roster effects as contextual until exact player/team/competition IDs
  reconcile. A newly announced player is not automatically available, eligible,
  fit, or expected to start.

## Forecast and AI boundary

Golavo already owns match-winner probabilities, an exact-score matrix, BTTS,
and clean-sheet marginals through its deterministic/statistical engine. The
match-analysis schema requires a pre-kickoff cutoff and describes the
explanation as descriptive, hypothetical, non-causal, and unable to average or
alter the sealed forecast.
([match-analysis schema](../contracts/match_analysis.schema.json))

An over/under 2.5 probability is mechanically derivable from the same full joint
score matrix by summing cells whose total goals are above or below the threshold.
That derivation should be implemented and tested in the deterministic engine,
versioned in the contract, and included in the numeric whitelist. It should not
be calculated by the local language model or copied from a provider prediction.

Cards, corners, and player-scorer probabilities are not derivable from a
goals-only matrix. Each needs its own target definition, licensed point-in-time
history, competition/era coverage, missingness semantics, leakage guard,
time-split evaluation, calibration, and abstention threshold. A local model can
later explain those outputs only after the deterministic engine produces them.
It cannot use live prose or post-match facts to “correct” a pre-match number.
([Golavo AI provider rules](../../docs-site/src/content/docs/ai/providers.md),
[Golavo product trust contract](../../CLAUDE.md))

If external Sportmonks predictions are enabled, present them beside Golavo as an
attributed external opinion with provider fixture/type IDs, retrieval/update
time, and add-on coverage. Disagreement is information, not a reason to average,
reweight, override, or call either side verified.

## Open-source GitHub implementations worth studying

The repositories below were cloned and their license and relevant source/docs
were inspected at their 2026-08-30 heads. No code or sample data was copied into
Golavo by this research.

| Repository and inspected head | Code license | Reusable architecture | Boundary |
|---|---|---|---|
| [`OpenLigaDB/OpenLigaDB-Samples@cec5dd750004`](https://github.com/OpenLigaDB/OpenLigaDB-Samples/tree/cec5dd750004) | Apache-2.0 | Small official examples for exact league/season/group endpoint shapes, result-type IDs, and last-change checks | The Apache license covers the sample code. API data remains ODbL and must stay in Golavo's existing overlay namespace. |
| [`PySport/kloppy@51dbd38c4fb4`](https://github.com/PySport/kloppy/tree/51dbd38c4fb4) | BSD-3-Clause | Vendor-independent event/tracking model, provider-specific deserializers, explicit periods, teams, coordinate systems, orientation, and dataset flags | Borrow the adapter/core separation and typed missing-capability flags. Do not use a parser as permission to obtain proprietary provider bytes. |
| [`ML-KULeuven/socceraction@93a1242d46c1`](https://github.com/ML-KULeuven/socceraction/tree/93a1242d46c1) | MIT | Normalizes event streams into SPADL/atomic-SPADL and separates conversion from xT/VAEP action-value models | Useful for normalized internal event vocabulary and reproducible transformations. Its README says it is not actively developed, and its provider loaders grant no rights to Opta, Wyscout, Stats Perform, WhoScored, or StatsBomb data. |
| [`floodlight-sports/floodlight@699b7fa1e37f`](https://github.com/floodlight-sports/floodlight/tree/699b7fa1e37f) | MIT | Typed core objects for tracking, events, possession, ball state, teamsheets, and pitch geometry; synthetic sample data for tests; operations check required columns | Useful for capability-aware core types and synthetic fixtures. Provider parsers and open code do not license proprietary input data. |

These repositories support a Golavo architecture of
`provider response -> license-isolated raw receipt -> typed provider adapter ->
canonical event candidate -> deterministic feature/model`, with every arrow
capability-checked and provenance-preserving. Open source is implementation
inspiration, not a way to launder upstream sports-data rights.

## What can ship without provider credentials

| Capability | Credential-free status |
|---|---|
| Current top-five schedules and completed scores | **Available** only after the existing OpenFootball certified refresh activates the generation. |
| Existing deterministic winner/exact-score/BTTS/clean-sheet analysis | **Available** from current accepted data and contracts. |
| Over/under 2.5 analytical marginal | **Implementable without a provider** from the existing full score matrix, after a core contract/test change. |
| Current German result/goal overlay | **Available only when the user separately enables OpenLigaDB**; still keyless, ODbL-isolated, and display-only. |
| Live corners/cards, confirmed lineups, player availability/form | **Unavailable** without a connected, entitled Sportmonks account. |
| Player-to-score, cards, and corners predictions | **Unavailable** until a separately licensed historical corpus and validated deterministic model exist. |
| Current automatic transfer feed | **Unavailable** without Sportmonks or another separately approved provider. |
| Transfer payment breakdown | **Unavailable by default.** Primary club/issuer disclosures may be linked and later captured only through reviewed source-specific policies. |
| Local AI explanation | **Available** when the user has a local model, but it explains only engine-produced numbers and cited allowed facts. It adds no forecast. |

The no-credential UI can still ship a professional capability surface: show the
deterministic match analysis, an explicit connection state for richer match
facts, an empty transfer ledger with a clear connection action, and precise
unavailable reasons. It must not fill those gaps with scraping, language-model
guesses, stale mirrors, or provider marketing claims.

## License isolation and provenance contract

Every new provider-backed field should carry:

- provider/source ID, endpoint, provider fixture/team/player/transfer/type IDs;
- competition and season identity, retrieval time, upstream update/completion
  time, and provider state;
- capability/plan result, unit/type definition, and missingness reason;
- terms URL, terms review/version/hash, account domain, and recheck date;
- raw-response SHA-256 only if retention is separately approved;
- normalized-record schema version, transformation version, and revision link;
- display/model/export/settlement/AI-evidence permissions as explicit booleans,
  never implied by the presence of data.

Provider namespaces remain disjoint. A Sportmonks, OpenLigaDB, club-disclosure,
or future source record cannot overwrite a CC0 core row or inherit another
source's redistribution rights. Exact provider IDs may be mapped only after the
competition/season/date/home/away tuple agrees; duplicates, remaps, and
conflicts fail closed. Logos, photos, bookmaker links, affiliate tracking, and
credentials remain outside responses, logs, caches, exports, and crash reports.
([source registry classification](../../data/sources/registry.json),
[provenance-first corrections ADR](../adr/0008-provenance-first-corrections.md))

## Implementation and release gates

Before any rich-match or transfer feature is released:

1. Re-verify the provider terms, pricing, field coverage, and rate metadata with
   the user's actual account. Record exact league/season/fixture/player/transfer
   IDs and per-field null rates over multiple matchdays.
2. Exercise scheduled, live, half-time, postponed, cancelled, abandoned,
   completed, corrected, and deleted fixtures. Prove that a completed-match
   correction creates a display revision and never rewrites a seal.
3. Exercise predicted and confirmed lineups, no-lineup matches, missing
   statistics, sidelined rows, unknown players, provider-ID remaps, duplicate
   candidates, and quota exhaustion.
4. Exercise permanent transfers, loans, options/obligations, free transfers,
   null amount, future dates, provider corrections, and rumours. Prove that the
   UI never manufactures a payment breakdown from the provider amount string.
5. Verify foreground-only networking, Keychain storage, token redaction,
   disconnect/delete, offline launch, cancellation, `401/403`, `429`, timeout,
   and `5xx` behavior.
6. If durable provider storage is added, review the new license namespace,
   retention/deletion contract, raw/canonical hashes, correction history, and
   export exclusion before implementation.
7. If any new forecast target is added, require written model rights, a frozen
   reproducible corpus, point-in-time cutoffs, time-split validation,
   calibration, abstention, and deterministic numeric-whitelist coverage. AI
   remains downstream explanation only.
8. Review gambling-content, age, jurisdiction, consumer-protection, and app-store
   obligations separately. A sports-data provider's terms do not clear those
   product obligations.
9. Run Golavo's focused provider/provenance tests and full required gates,
   refresh Graphify, and verify exact release artifacts and public surfaces. A
   green build alone is not provider, licensing, or release proof.

## Primary sources reviewed

- Golavo's current [source registry](../../data/sources/registry.json),
  [OpenLigaDB isolation ADR](../adr/0005-openligadb-odbl-overlay.md),
  [research-capture ADR](../adr/0009-evidence-bound-research-extraction.md),
  [match-analysis schema](../contracts/match_analysis.schema.json), and
  [AI-provider contract](../../docs-site/src/content/docs/ai/providers.md).
- Sportmonks' first-party
  [fixtures](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/fixtures),
  [live updates](https://docs.sportmonks.com/v3/world-cup-2026/live-matches-livescores-and-events),
  [lineups](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/lineups-and-formations),
  [statistics](https://docs.sportmonks.com/v3/definitions/types/statistics),
  [transfers](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/transfers),
  [corrections](https://docs.sportmonks.com/v3/api/data-corrections),
  [rate limits](https://docs.sportmonks.com/v3/api/rate-limit),
  [pricing](https://www.sportmonks.com/football-api/), and
  [terms](https://www.sportmonks.com/terms-of-service/).
- OpenFootball's [project and format](https://openfootball.github.io/) and
  [CC0 dedication](https://github.com/openfootball/england/blob/master/LICENSE.md);
  OpenLigaDB's [official API samples](https://github.com/OpenLigaDB/OpenLigaDB-Samples),
  [Swagger](https://api.openligadb.de/index.html), and
  [ODbL/keyless-access statement](https://beta.openligadb.de/).
- First-party alternative-provider documentation and terms linked in the
  comparison table; Transfermarkt's own terms; FIFA's legal and Clearing House
  materials; the Juventus issuer filing; and the four directly inspected GitHub
  repositories listed above.

No provider token was used, no live commercial-provider response was fetched,
and no source dataset was added to Golavo. Temporary shallow code-repository
clones were used only to inspect the four open-source implementations above; no
scraper or undocumented endpoint was exercised. Provider prices, plans,
coverage, terms, and schemas can change; re-verify them before implementation or
release.
