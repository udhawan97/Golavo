# Changelog

All notable changes to Golavo are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.15.0] - 2026-07-16

Golavo 0.15.0 is an architecture release. Three rules that the app had been keeping in
several places at once — where a forecast's information cutoff comes from, when a cached
answer stops being current, and which model families are voices — now each live in exactly
one place. Forecasts, sources, and the seal→score loop are unchanged; the committed sample
artifacts reproduce byte-for-byte.

### Changed
- **The leak-safe training view is one module.** A fixture's `kickoff - 1s` cutoff, the
  scoping of history to that fixture's own source, the exclusion of its own row, and the
  no-future-rows guard are now inseparable in `golavo_core.ingest.leak_safe_training_view`.
  The cutoff was previously derived in four places and the source scoping existed twice —
  verbatim, in the server's analysis path and in the core retrospective — kept in agreement
  by a comment. The seal path uses the same module, with `min(as_of, kickoff - 1s)`.
- **Cached reads share one implementation.** Every derived read over the match index
  (outlook, season outlook, match analysis, competition analytics, conditions, the
  retrospective) now goes through one `SnapshotReader`, which owns the repoint retry, the
  cache key, the publish gate, the provenance stamp, and its own invalidation. `matches`
  no longer hardcodes the names of the modules that cache on top of it — a new cached read
  cannot be forgotten and quietly serve a retired data generation after a refresh.
- **Tracked work runs in named lanes.** Each kind of background job (AI read, World Cup
  retrospective, model download) declares its own stage vocabulary and job-id space, so a
  job reports its real stage from the moment it starts and one lane's cancel door cannot
  reach another lane's job.
- **The trust table's voices are chosen once.** The retrospective's skill fold is now
  served already projected onto the four voices the backtest offers, with anything dropped
  named in a new required `omitted_families` field
  (`docs/contracts/tournament_retrospective.schema.json`). The rule previously lived in
  both the core and the React view, which could disagree.
- Competition analytics resolves its as-of to the minute and caches per minute, matching
  the outlook surfaces. Previously it recomputed on every request against the wall clock.

## [0.14.2] - 2026-07-16

Golavo 0.14.2 brings the 2026 World Cup final into the app, closes a training-data leak
that the tournament's exact kickoff times made reachable, and adds a retrospective that
backtests every played match of the tournament.

### Fixed
- Forecasts no longer train on matches played later the same day. Training rows were
  selected by calendar date, which treats every fixture on a day as simultaneous, so a
  result from 20:00 could inform a forecast for a match that kicked off at 00:30 — and the
  leakage guard compared the same dates, so it could not see it. **Replays on days with
  several matches will differ from 0.14.1: they previously used information that did not
  exist yet.** Sealed forecasts were never affected, because a match played later that day
  is not complete when a seal is written, and evaluation folds cut on day boundaries.
- The World Cup outlook no longer treats a semifinal as decided when its kickoff has not
  passed at the requested cutoff. A snapshot carrying the result of a later match could
  report that match complete, and pin its winner into the bracket, for a cutoff before it
  was played.

### Added
- The 2026 World Cup final and third-place match, with exact kickoff times, so the seal
  window stays open until the whistle rather than closing at midnight the night before.
  Both semifinals now carry their results.
- A World Cup 2026 retrospective in Model Lab (`Model Lab → World Cup 2026 retrospective`).
  It replays every played match of the tournament at that match's own pre-kickoff cutoff —
  the same cutoff a seal uses — and ranks them by how surprised the goal model was, beside
  the tournament's evaluation fold answering whether the models had skill at all.
  Every number on the page is a backtest, not a record: nothing there was called in advance
  by anyone, and nothing is persisted or scored as a seal. Computed on demand from your
  active data (a few minutes, with progress and cancellation) and cached until that data
  changes. Rows whose training data includes a same-day date-proxy kickoff are marked,
  because their ordering within the day cannot be proven.

## [0.14.1] - 2026-07-16

Golavo 0.14.1 repairs installed-app result refresh and gives match conditions a
clearer, more visual structure without changing forecasts or source boundaries.

### Fixed
- Packaged approved-source refresh now uses a bundled CA trust store instead of a
  build-machine OpenSSL path, so HTTPS refresh works from an installed app.
- Refresh generations retain previously verified completed evidence across upstream
  removals, preserve stable fixture ids across venue-label corrections, and accept
  equivalent completed-row deduplication without weakening score-change guards.
- My Season and Pick History reload scores, totals, and settled picks immediately
  after a refreshed data generation is activated.
- First-launch tours now yield to update notifications and update sheets, so enabling
  update checks cannot place a modal tour over the newly available release action.

### Changed
- Conditions Snapshot now uses icon-led fact cards, explicit coverage status, aligned
  recovery timelines, structured travel details, subtle pitch-grid texture, and an
  intentional route-map empty state. Provenance and the display-only model boundary
  remain visible and unchanged.

## [0.14.0] - 2026-07-16

Golavo 0.14.0 completes the source-aware local data loop and makes the deterministic
Match Cockpit easier to interrogate without changing a model or overstating source truth.

### Added
- Consent-gated approved-source refresh with immutable raw receipts, parser/schema gates,
  atomic two-generation activation, source health, cancellation, and last-known-good use.
- An optional per-user OpenLigaDB ODbL overlay for allowlisted German competitions. It is
  display-only, physically isolated, attributed, unbundled, removable, and prohibited from
  core indexes, models, calibration, settlement and exports.
- Source-backed place, venue, local-kickoff, rest and travel context using a compact
  unique-exact GeoNames place table, revision-pinned Wikidata venues, and a lightweight
  offline Natural Earth route map.
- Local followed matches with targeted while-open refresh, deduplicated change history and
  optional local notifications; no daemon, Login Item, LaunchAgent, account or cloud sync.
- A provenance-first correction queue with evidence receipts, immutable event history,
  fail-closed conflicts, license namespaces, local display annotations and explicit export.
- Consent-gated selected-source research with immutable captures, deterministic parsing,
  optional local-AI fallback, cancellation/resume and correction-queue handoff.
- Deterministic Match Cockpit explanations for history support, exact model-voice gaps,
  capability coverage, missing evidence and hypothetical change triggers.

### Changed
- DuckDuckGo HTML discovery is disabled; search discovers candidate Wikimedia pages only
  and can never make a fact authoritative.
- Match analysis cache entries are schema-, match-, index- and hash-bound. Invalid or stale
  entries recompute, while repeat navigation stays fast and Phase 8 adds no model fit.
- Sparse forward reliability stays hidden until at least 100 seals and three probability bins
  with 20 or more observations each; seal lead time now comes from immutable timestamps instead
  of a coarse horizon tag.
- README and documentation now describe every landed local-data boundary, enlarge the logo,
  stack the Match Cockpit animation at full width, and repair the architecture SVG label.

### Security and release
- Research fetches fail closed on unapproved hosts/paths, private IPs, redirect drift, DNS
  rebinding, oversized/slow responses, hostile markup, prompt injection and quote mismatch.
- Correction candidates are integrity-checked again at the queue boundary; AI research has no
  probability, pack, training, calibration, settlement or seal write path.
- Packaged builds embed and expose their exact source commit. The release workflow now blocks
  packaging on the complete Python, determinism, provenance, isolation, UI and docs gates.
- Update recovery prunes obsolete retired ledger generations while retaining the newest one.

## [0.13.0] - 2026-07-15

Golavo 0.13.0 expands the local match library into a competition intelligence
workspace while keeping forecasts, simulations, historical research, and
display-only context in separate, typed lanes.

### Added
- **Competition analytics.** Domestic leagues and UEFA club competitions now
  expose competition-local strength trends and rest/congestion context. Model
  report cards use chronological held-out folds with bootstrap intervals;
  schedule difficulty stays blocked without a complete fixture list.
- **World Cup and domestic season outlooks.** The resolved four-team World Cup
  bracket is exactly enumerated for Ratings, Goals, and a baseline under a
  disclosed knockout rule. Five domestic rule sets reproduce the latest common
  complete season, while the 10,000-run current-season outlook fails closed
  until every fixture and past result is certified.
- **Offline Conditions Snapshot.** Pinned GeoNames and Natural Earth resources
  provide local kickoff, elevation, rest, great-circle travel, and route maps
  where exact city evidence exists. Weather is a first-class blocked context
  until a licensed, issued-before-kickoff historical forecast source exists.
- **Historical team research.** Seven isolated Pappalardo/Wyscout CC-BY-4.0
  artifacts summarize all 1,941 matches and 3,251,294 events by competition and
  era. Progressive passing, shot rates, an event-run proxy, and research xT are
  team-only, collapsed by default, and never enter a forecast or simulation.
- **European competition coverage.** Champions League, Europa League, and
  Conference League historical main-competition results now have stable
  identities, browse pages, strength trends, and workload context.

### Changed
- The Leagues hub now uses mutually exclusive **International tournaments**,
  **Domestic leagues**, and **UEFA club competitions** sections.
- Analytics use explicit competition identities, format eras, capability states,
  license classes, and versioned JSON contracts throughout the core, API, UI,
  frozen sidecar, docs, and source registries.

### Fixed
- World Cup 2026 no longer appears under Domestic leagues or in two hub groups.
- Outlook caches now invalidate with the active match index and cannot reuse a
  result fitted against another in-memory frame.
- Incomplete La Liga and Serie A captures render typed past-result gaps instead
  of a fabricated final table or zero-filled season projection.

### Verification
- User flows were exercised in the connected local app for league grouping,
  outlook voice switching, blocked fixture states, mobile table containment,
  research disclosure/team selection, and weather fail-closed behavior.
- Full core/server/script, UI, docs-site, source-governance, version, packaging,
  and release gates are required before the v0.13.0 tag is published.

## [0.12.0] - 2026-07-14

The Match Cockpit now reads like a six-chapter matchday programme: the same
deterministic evidence, shaped into a calmer Casual read with full Expert depth
available in the same order.

### Added
- **A six-chapter matchday programme.** Form, style, history, model deliberation,
  verdict and pick, and the optional analyst column now form one editorial read
  with chapter mastheads, fixed-rule pull numbers, inline sparklines, ruled
  dividers, and a source-backed colophon.
- **The engine's hidden depth is now visible.** Expert mode exposes fitted Elo and
  Dixon–Coles parameters with plain-language definitions, while the form book adds
  venue markers, opponents, deterministic streaks, and last-five goal-difference
  trends.
- **A fuller Score Outlook.** Double chance, match-total thresholds, and the
  home/draw/away split beyond the displayed score grid join the existing goal-line,
  clean-sheet, distribution, and exact-score views.
- **Timing and discipline context.** Guarded goal-timing profiles render as compact
  minute-band timelines, with the engine-provided penalty-goal share alongside
  them when the notebook contains that fact.

### Changed
- **Casual and Expert now share one reading rhythm.** Casual keeps each new signal
  to a short takeaway or compact chart; Expert preserves the fitted values and all
  market rows without changing their order or the underlying probabilities.
- **The verdict keeps the final word.** The score outlook, pick, seal flow, and AI
  column remain subordinate to the deterministic model council, with every number
  still supplied by the engine or its existing market helpers.
- **Release presentation refreshed.** The README and documentation site now use
  current Match Cockpit screenshots and an animated tour of the programme.

### Fixed
- **Deep analysis keeps the complete evidence.** Ollama context sizing now leaves
  room for both the full match prompt and its structured answer, preventing the
  silent evidence truncation or HTTP 500 that could strand a read until the
  12-minute UI deadline. Context failures retry with the compact guarded bundle,
  and a sidecar restart now reports a lost job promptly instead of posing as a
  model timeout.

### Accessibility
- Pull numbers have meaningful accessible labels, inline SVGs retain adjacent text
  equivalents, chapter introductions remain plain aligned text, and all new charts
  use the existing theme-safe outcome tokens with reduced-motion behavior unchanged.

## [0.11.1] - 2026-07-14

Golavo's first launch, match browsing, and sealed-forecast audit now share a
clearer visual hierarchy without changing any deterministic forecast values.

### Changed
- **First launch is easier to trust.** Startup now distinguishes unpacking,
  engine startup, and match-index warming with stage-specific reassurance,
  elapsed-time context, and a polished branded presentation that respects
  reduced-motion preferences.
- **Matchday cards are faster to scan.** A responsive three/two/one-column grid,
  compact team marks, clearer fixture state, venue treatment, and contained
  hover/focus behavior improve desktop and mobile browsing.
- **Forecast and seal are one commitment.** The sealed outcome bucket and most
  likely individual scoreline are shown together, with an explicit explanation
  that a result probability combines many scorelines. Human-readable seal facts
  stay visible while seed and hashes move into a verification disclosure.

### Fixed
- Long club names now step down before they crowd the protected score lane, with
  deliberate spacing preserved on both sides at phone and desktop widths.
- Failed update checks now open the GitHub releases page through the operating
  system browser from both signed-updater and unsigned/local fallback states.
- Outcome percentages use the same sum-to-100 rounding as the probability bar,
  removing cases where the prominent forecast and plain-language summary could
  disagree by one percentage point.

## [0.10.3] - 2026-07-14

### Fixed
- AI verdicts now show the actual home team, away team, or **Draw** instead of
  leaking internal `home` / `away` outcome tokens into the reader-facing card.
  Existing citations remain attached to the corrected label.
- Deep analysis now keeps the **At a glance** winner card when a local model
  omits its optional verdict, falling back to the deterministic engine's leading
  outcome and clearly labelling that fallback as an engine result.
- The verdict card now always names the deterministic **Engine pick** when one
  exists, even if the local model uses its verdict field for supporting analysis.
- The narration prompt now explicitly requires real team names in the verdict,
  and its version was advanced so cached local-model responses are regenerated.

## [0.10.2] - 2026-07-14

The goal model's deeper score read is now a glanceable market dashboard instead
of a flat list, while every probability still comes from the deterministic engine.

### Added
- **Focused Score Outlook coverage.** Component tests protect the summary cards,
  total-goal distribution, expected-total marker, and exact-score disclosure.
- **A shared branded horizon.** The startup, recovery, and website landing screens
  now carry the README icon's blue seigaiha waves, with theme-aware contrast, a
  calm drift, and a static reduced-motion presentation.

### Changed
- **Score Outlook, redesigned.** More markets opens with a compact preview of the
  most balanced O/U line, clean-sheet edge, and goal peak, then reveals polished
  O/U bars, clean-sheet comparisons, and a total-goal distribution.
- **Exact-score detail is calmer.** The full matrix remains available behind a
  clear disclosure, keeping the first read compact without deleting model detail.
- **Motion and small screens are deliberate.** The first-open animation uses one
  animation loop, respects reduced-motion preferences, and the dashboard collapses
  cleanly on narrow viewports.

### Fixed
- Equal clean-sheet probabilities are now labelled **level** instead of assigning
  a false edge to the home team.

## [0.10.0] - 2026-07-14

Local AI is now something a casual user can set up and understand inside Golavo.
The Analyst Read and Commentator's Notebook are calmer and more visual, Fast and
Deep have clearly different jobs, and Ollama models can be installed without a
terminal while Golavo shows exactly what is running.

### Added
- **Guided Ollama setup.** A three-step guide appears in Settings even while AI is
  off, and a compact copy sits beside the match analysis controls. It links to the
  official macOS installer and help, checks whether Ollama is running, and explains
  the local-only privacy boundary in plain language.
- **In-app local model downloads.** Golavo offers a curated Fast model
  (`llama3.2:latest`, about 2.0 GB) and Deep model (`gemma4:12b-it-qat`, about
  7.2 GB), streams real Ollama download progress, shows transferred bytes, and lets
  the user cancel. Downloads never begin automatically.
- **One-click model assignment.** Choosing or installing a recommended model enables
  Local · Ollama and assigns it to Fast or Deep. Installed models are detected and
  marked Ready; the full picker remains available for custom assignments.
- **Visible local-AI readiness.** The analysis panel distinguishes Ollama being off,
  Ollama running with no models, and usable installed models, with a real re-check
  path after the user starts the local service.
- **Quick web-research control.** The opt-in web-search checkbox now lives beside the
  analysis controls as well as in Settings, so network use is visible at the moment
  a read is requested.

### Changed
- **AI Analyst Read, rebuilt for scanning.** The result is structured as a verdict,
  key findings, scenario cards, clearly separated analyst research, and expandable
  evidence rather than a long undifferentiated text wall.
- **Commentator's Notebook, rebuilt for scanning.** Predictive, context, and
  coincidence material is grouped into visual sections with compact stat cards,
  dials, icons, comparison colour, and progressive disclosure for exact wording,
  date ranges, samples, and sources.
- **Fast and Deep are meaningfully different.** Fast uses the smaller assigned model
  for a short grounded read; Deep gives the larger assigned model more evidence and
  asks for connected scenarios, while honestly warning that the full run usually
  takes 5–8 minutes.
- **Local response recovery is more resilient.** Ollama output uses native structured
  decoding, preserves multi-source evidence, and can recover safe JSON from common
  wrapper or truncation shapes before the same numeric/source verification runs.
  Unsupported content still fails closed to deterministic analysis only.
- **Header AI control polished.** The local-AI indicator is contained, aligned with
  the other header actions, and reports the configured provider without decorative
  overflow.

### Fixed
- External links in the packaged desktop app now open in the system browser,
  including Releases, Documentation, Ollama help, update fallbacks, and cited
  sources.
- Fast analysis now labels its active model as **Basic** instead of showing the
  Deep mode's **Advanced** label.
- Long club names wrap within match cards instead of bleeding past the card edge.

## [0.9.0] - 2026-07-14

Your score call now has its own honest game: pick before kickoff, prove the locked
record stayed unchanged, and race five deterministic model rivals across My Season.
The cockpit's evidence also moves into a calmer, editorial Match Notes read.

### Added
- **Your Call.** Upcoming matches have an editable 0–0 score ticket. Calls lock at
  kickoff (or the start of a date-only match day), receive a canonical SHA-256
  fingerprint, survive restarts in the local ledger, and score after full time.
- **Transparent points race.** Exact score earns 3, the right outcome earns 1, and
  strictly beating every available model earns a +1 bonus. Rival calls are derived
  from stored model outputs, hidden until the user saves, and pinned at lock time.
- **My Season.** A private dashboard tracks points, exact scores, outcomes, bonuses,
  streaks, standings, cumulative progress, and pick history against five named rivals.
- **Picks API and contract.** A versioned, additional-properties-closed pick schema;
  durable draft/locked storage; typed GET/PUT/DELETE/list/summary endpoints; atomic
  writes; one process lock; fixture-key fallback; integrity verification; and audit
  events. Web preview uses clearly labelled, device-local practice records.
- **Picks guide and onboarding.** A five-step worked example, simple 3 / 1 / +1
  explanation, no-gambling FAQ, new tour anchors, and plain separation between the
  user's game and expert forecast sealing.
- **Match Notes.** Form timelines, fitted style, scorer and head-to-head features,
  numbered signature facts, quarantined coincidences, and source/suppression folios
  now share one magazine-style evidence surface. A strict formation parser and
  display-only mini-pitch are ready for future typed enrichment.

### Changed
- Expert forecast sealing is a quiet cockpit row in Casual mode and retains its full
  provenance treatment in Expert mode.
- The optional API-Football/BYOK formation adapter is deferred to v0.9.1 until real
  free-season coverage and quota headers can be verified with a user-owned key. Picks,
  models, sealed artifacts, and AI evidence do not depend on it.

## [0.8.0] - 2026-07-14

Half-time scores now tell the second-half story for club matches, while World Cup
fixtures gain a leak-safe pedigree shelf sourced from an isolated, credited history
pack. Both additions remain deterministic facts; neither changes the forecast model.

### Added
- **Second-half story.** Played club matches with recorded half-time scores show each
  side's saved-from-behind and leads-kept records, with honest sample counts and no
  invented coverage for older seasons that lack half-time data.
- **World Cup pedigree.** Exact `FIFA World Cup` match pages show titles, finals,
  appearances, best recent finish, and individual awards. Historical replays are
  filtered by tournament end date, so a 2014 view cannot surface 2018 evidence.
- **Isolated World Cup history pack.** The pinned Fjelstul World Cup Database pack is
  vendored under `CC-BY-SA-4.0`, validated by manifest hashes, kept out of the CC0
  joined match index, and credited in the data docs and third-party notices.

### Changed
- Match-index schema `0.2.0 → 0.3.0`, adding nullable half-time home/away scores at
  the end of the schema without changing any match identity.
- Deterministic fact family `44 → 52`, adding four half-time and four World Cup fact
  candidates with structured, source-scoped evidence for the optional AI read.

## [0.7.0] - 2026-07-14

A smarter, more polished AI read: it now leads with a one-line **verdict**, connects
the evidence instead of restating it, can **research the fixture on the web** (opt-in),
and shows **real progress** while it works. The cockpit gained new analytics, and the
deterministic notebook surfaces new "hidden" stats — all still engine-verified.

### Added
- **AI verdict + deeper synthesis.** Every read opens with a one-line most-likely
  outcome ("Spain to win — 41.6%", engine-verified), then claims that *connect* at
  least two pieces of evidence — tensions between the models, corroborations,
  historical analogues — instead of restating a number the reader already sees.
- **Web research lane (opt-in, off by default).** With "Let the AI research on the
  web" on, a read fetches a few **Wikipedia** pages and a **web search** for the
  fixture and adds a clearly-separated **"Analyst research"** section. It is badged
  **not engine-verified**: each finding must quote the fetched page verbatim, and its
  numbers are checked against that quote — never against the engine. The grounded read
  keeps its hard guarantee. Web search is best-effort and falls back to Wikipedia-only.
  This is the only setting that lets the app reach the general web; fetches are
  https-only against a host allowlist with a proper User-Agent.
- **Real, server-reported progress.** The long Deep read now shows genuine stages
  (assembling → researching → writing → verifying) with a live detail line
  ("Reading: … — Wikipedia") and source counts, driven by a new
  `GET /api/v1/ai/jobs/{id}` poll — no more guessed progress bar. Includes a cancel
  action and a graceful simulated fallback for older sidecars.
- **New cockpit analytics.** Both-teams-to-score and clean-sheet probabilities
  (exact, from the goal model's full matrix), over/under goal lines and total-goal
  bands, an **outcome-range band** showing where the model voices land, and
  **expected goals against** in the team-style profile.
- **New deterministic facts** from data already shipped: goal-timing skew
  (opening/closing-stage scoring), penalty share of goals (scored penalties only),
  own-goal curios, all-time record in the fixture's competition (e.g. World-Cup-only
  form), and the penalty-shootout first-taker edge.
- **First-launch spotlight tour.** A short, dependency-free coach-mark tour points
  out the real UI on a fresh install: a home tour (open a match → Model Lab → local
  AI in Settings) and, the first time a match is opened, a cockpit tour (the model
  council → the notebook → the Fast/Deep AI read). It only fires when its target
  actually exists (never over a still-warming, empty home), yields to the update
  consent card, is seeded "done" for existing users so an update never replays it,
  and is fully keyboard- and screen-reader-navigable. Replay it anytime from
  Settings → Getting started. Desktop only.

### Changed
- **AI Analyst Read, redesigned.** The wall of repeated citation chips is gone: claims
  read as editorial prose with small footnote markers, and every source is listed once
  in a deduplicated **"Evidence used"** legend with per-source cited counts. A gold-lit
  verdict hero, scenario bullets, a staged "AI at work" animation, and generous spacing
  replace the cramped layout.
- **Citations now vary by dataset.** A scorer or shootout fact is attributed to the
  specific pack file it came from (results / goalscorers / shootouts), so the AI's
  citations are no longer all identical.
- Match-analysis schema `0.4.0 → 0.4.1` (additive `derived_markets`); AI narration
  schema `0.2.0 → 0.3.0` (additive `verdict` + `research_notes`); fact registry
  `2026.07.13 → 2026.07.14` (family size 35 → 44, still a fixed pre-registered
  constant). The prompt version bump rolls the narration cache.
- **A slow first launch never looks like a failure.** The engine self-extracts on
  first run, which can take past a minute; the splash now stays calm and patient
  (wider on a first launch, tighter afterwards), shows a reassuring "still working,
  nothing is wrong" note with elapsed time instead of an alarming stall screen, and
  only offers a retry once the shell actually reports a failure.
- **The engine restarts itself before ever showing an error.** If the local engine
  stops before it is ready, the app silently restarts it once; only a second
  failure surfaces a calm, focused "Try again" (which truly restarts the engine,
  not just a timer). The shell keeps the window alive and hands the failure to the
  UI rather than dying in a native dialog, and it no longer kills a slow-but-healthy
  launch to "retry" it.

### Notes
- Half-time/comeback club stats and the CC-BY-SA World Cup history pack are planned
  follow-ups (they involve a committed-index rebuild and licensing sign-off).

## [0.6.0] - 2026-07-13

Two-speed local AI: a **Fast** fallback for a quick read and a genuinely deeper
**Deep analysis** that puts a bigger local model to work — a richer synthesis, not
the same answer slower.

### Added
- **Fast / Deep local AI.** A toggle on the AI read chooses the speed. **Fast**
  runs a small model (e.g. `llama3.2`) for a few grounded claims in seconds.
  **Deep analysis** runs a bigger model (e.g. `gemma4:12b`) over MORE of the
  evidence with a richer-synthesis instruction — more claims plus scenarios that
  connect facts to each other and surface tensions and corroborations — in a few
  minutes (up to an 8-minute budget). The progress note is honest about the wait,
  and a one-tap **Switch to Fast** (which also starts the fast read) recovers if a
  deep read times out.
- **Assign your models.** Settings → Local intelligence lists your installed
  models with sizes and lets you pick which one runs Fast and which runs Deep
  (auto-set to smallest and largest). An "advanced" control on the panel runs any
  specific installed model for a single read. New read-only `GET
  /api/v1/ai/local-models`.
- Under the hood: the Ollama path now uses the native `/api/chat` structured-output
  endpoint (its `format` grammar constrains **every** model, `think:false` stops a
  reasoning model wasting minutes), the context window is sized to the prompt, and
  decoding is **enum-constrained** to the bundle's real citation ids. The prompt is
  trimmed (~40k→~11k chars) so a model fits context and stays fast.

### Changed
- The optional AI read is more forgiving of natural analytical prose so a single
  idiom no longer blanks the whole read: betting language and an unsupported number
  are dropped per-claim instead of hard-rejecting the entire narration; an
  over-tagged number reference (one the model alluded to but didn't state) is
  pruned rather than fatal; "edge" is no longer treated as a wagering term. The
  guarantee is unchanged — every number is validated against the full sealed
  whitelist and a dropped claim's content is never shown.
- A local model that times out is no longer retried (an immediate retry just
  doubles the wait).

## [0.5.2] - 2026-07-13

Makes the optional local AI read actually produce output on the Match Cockpit,
where a small local model faced with the large council+notebook bundle would
otherwise return nothing.

### Fixed
- **The AI Analyst Read now works with local models on rich matches.** Faced with
  the big evidence bundle, a small local model would parrot the bundle back under
  a wrapper key instead of the required shape, so every attempt failed schema
  validation ("'claims' is a required property") and the panel showed only the
  deterministic analysis. Golavo now constrains local/OpenAI decoding to the
  narration schema (`response_format: json_schema`, with a safe fallback for
  servers that don't support it) and sharpens the prompt, so the model returns
  the right `{claims, scenarios, candidate_facts}` shape.
- **One wrong number no longer blanks the whole read.** If a model states a figure
  that doesn't exactly match the engine's sealed number, that single claim is now
  dropped (its number never shown) while the other verified claims stand — instead
  of hard-rejecting the entire narration. The number guarantee is unchanged: a
  claim survives only if every figure exactly matches a cited engine number.
- Fixed a false positive where "both" (as in "both teams scored") was treated as
  the number 2 and dropped an otherwise-correct claim.

## [0.5.1] - 2026-07-13

Local AI now just works with whatever model you have, fails honestly when it
can't, and a batch of user-flow gaps around the optional AI read are closed. The
deterministic engine and every number are unchanged — these are reliability and
clarity fixes to the optional layer on top.

### Fixed
- **Local AI works with the model you actually have.** The app only ever asked
  the local server for its built-in default model (`llama3.1`); if you hadn't
  pulled that exact model, Ollama/llama.cpp returned "model not found" and the
  read looped forever on "AI output could not be verified." Golavo now probes the
  local server's installed models and runs the closest match (preferring the same
  family), so it works out of the box with any model you've pulled. Set
  `GOLAVO_OLLAMA_MODEL` / `GOLAVO_LLAMACPP_MODEL` to pin a specific one.
- **Honest failures instead of a silent loop.** When no local model is reachable
  you get a clear, actionable message (start the server / pull a model) with a
  working **Try again** button — previously a dead end. The "showing the local
  forecast only" reason now distinguishes *couldn't reach the model / timed out*
  from *the model answered but its output failed the guards*, and the real
  reasons are shown under a "What happened" disclosure. Raw `HTTP 503` no longer
  leaks to the screen; it shows an "engine still warming up" hint instead.
- **A cached AI read survives the local server being stopped**, instead of
  flipping to "unavailable." Truncated local/cloud responses now fall back
  cleanly rather than erroring, and an embedding-only local install reports "no
  usable model" instead of looping on garbage output.
- **A corrupt notebook file can no longer 500 the AI read** — it fails closed and
  is treated as "no notebook," so the forecast read still works.
- The loading animation no longer resets its checklist to the first step (which
  read as "restarting"); local models get a longer default timeout to load.

### Changed
- Small local models that decorate their JSON with harmless extra keys, or return
  a slightly-off optional "background" note, no longer have their whole (otherwise
  valid) answer thrown away — extras are pruned and bad background notes are
  dropped individually, with the grounded, cited claims preserved.
- The betting-lexicon and credential scanners now fold Unicode look-alikes and
  strip zero-width characters, closing an obfuscation gap in the AI guards.

## [0.5.0] - 2026-07-13

Free/open expansion, phase one: attribution and licensing become machine-checked,
World Cup seals close at the real kickoff, and the 2026 semifinals are sealable —
supplied by CC0 worldcup.json where martj42 hasn't published them yet, always
trained on martj42 history, with both sources named in every artifact.

### Added
- **Source registry & attribution gates (Phase 0).** `data/sources/registry.json`
  (schema-validated) is now the machine-readable record of every dataset Golavo
  carries, plans, or has rejected — contributors, license, license URL, and a
  license classification. `scripts/validate_sources.py` (in CI) ties it to the
  bundled packs, so an unregistered, misclassified, or license-mismatched source
  fails before it can reach the index. `THIRD_PARTY_NOTICES.md` is generated from
  the registry (CI `--check`), `LICENSES/` carries the full CC0/Apache texts, and
  the first Hypothesis property tests fuzz probability canonicalization and the
  training-cutoff invariant. The full free/open expansion plan lives in
  `docs/handoff/expansion-plan.md`.
- **Exact World Cup kickoff times.** A pack may carry an optional,
  manifest-declared `kickoffs.csv` overlay (built from CC0
  openfootball/worldcup.json by `scripts/build_worldcup_overlay.py`) that
  `load_matches` splices onto matching internationals rows, so a World Cup seal's
  window closes at the real kickoff instead of the conservative 00:00 UTC day
  proxy. Completed results are cross-checked against martj42 and the build fails
  closed on any disagreement; `is_complete` is untouched so upcoming fixtures
  never enter training; and a pack without the overlay is byte-for-byte unchanged
  (the committed index too).
- **The 2026 World Cup semifinals are sealable.** martj42 hasn't published the
  semifinals yet, so the refreshed internationals pack now also carries the
  scheduled World Cup fixtures worldcup.json has but martj42 lacks (France–Spain,
  England–Argentina), added as internationals rows with exact kickoffs.
  `build_forecast_artifact` trains only on martj42's results and records BOTH
  sources in each artifact's provenance (martj42 as the training source,
  worldcup.json as the fixture/kickoff co-source); `resolve_pack_dir` now selects
  the greatest-anchor bundled pack so search and sealing stay on one source of
  truth. `scripts/build_worldcup_refresh.py` builds the pack (cross-checking every
  completed result against martj42, failing closed on disagreement), and the
  source registry, notices, and license gate now cover bundled co-sources.

### Fixed
- Cleared the ruff violations v0.4.0 left on `main` (line lengths, an import
  sort, `datetime.UTC`, and an unbound loop variable in the in_form_scorer
  template), all behavior-preserving, restoring a green lint gate.
- Doc truth: SUPERSEDED banner on the architecture-rethink plan (its Phase 0/1
  shipped in v0.3.x), corrected DuckDB "warehouse" language that was never a
  dependency, and removed the false clippy-in-CI CHANGELOG claim.

## [0.4.0] - 2026-07-13

An analytics-first elevation: the wait is honest and informative, the home leads
with real matches, and the Match Cockpit becomes the showcase — a multi-model
read with form, team style, and source-backed notes on every game. Every sealed
number is unchanged.

### Added
- **Honest, staged startup.** A new `GET /api/v1/status` reports the match-index
  warm-up state (without triggering the slow load), so the splash shows real
  stages — "unpacking the engine" then "waking the match library" — with a
  rotating deck of witty wait-copy, hidden-feature tips, and football facts. A
  "browse while it warms" escape and a home warming card replace the old
  flashing skeletons; the matches query now waits for the index instead of
  blocking ~25s inside it. A header activity centre surfaces live background work
  (warm-up, update download, fixture checks) and hides when idle.
- **Matchday home (was Games).** Leads with finished results from the last week
  (anchored to the freshest result in the snapshot, so a stale bundle degrades
  honestly), with Last week / Last month / Upcoming filters, grouped by
  competition with the big-five leagues and major internationals first. Every
  card links to its Match Cockpit and shows an "Analyze" affordance.
- **Match Cockpit showcase.** Recent-form strips (last-5 W/D/L per side), a
  "how they attack & defend" style profile (fitted-from-results multipliers,
  honestly labelled — no event data exists), a dedicated score outlook, and a
  categorised Commentator's Notebook (Form / Head-to-head / Records / Signature).
  A new `in_form_scorer` fact highlights a team's hot scorer (internationals).
- **Sealing guide.** A plain-language `#/guide/sealing` page — pick → read
  council → seal → scored → track record — with one annotated synthetic example.
- **Optional AI background lane.** On top of the strictly-grounded read, the model
  may add qualitative colour (managers, style, rivalries) from its own general
  knowledge — off by default, clearly badged as not-Golavo-data and may-be-
  outdated, and forbidden from stating any number (anything numeric is deleted).

### Changed
- **Sealing is a small side feature now**, not the front door: a compact prompt on
  match pages plus the new guide, and synthetic samples are never shown as data
  (an empty ledger shows an empty list; the desktop sample banner is gone).
- **Faster cockpits.** A content-addressed disk cache and a background warm of the
  home-window matches mean re-opening a match skips the five model fits.

## [0.3.3] - 2026-07-12

A polish-and-hardening pass from a full UX audit: fewer sharp edges, plainer
words, a calmer surface, a faster first paint, and docs that finally match the
post-pivot app. No new forecasting behaviour — every number is unchanged.

### Fixed
- **A malformed deep link no longer white-screens the app.** Route decoding is
  guarded and a top-level error boundary catches any render-time throw, degrading
  to a recoverable panel instead of a blank page.
- **The startup splash can no longer hang forever.** If the local engine doesn't
  answer within ~30s the splash offers a retry and guidance, and the health
  probe times out instead of pending indefinitely.
- **The AI narrative route no longer blocks the event loop** — its model call
  runs off-thread, so a slow narration can't stall `/health` (which the startup
  gate and updater poll) or any other request.
- **The reading-comfort popover stays on screen on mobile** — it pins to the
  viewport at narrow widths instead of spilling off the left edge.
- **No more "Played · in 1282 days."** Relative kickoff times only show inside a
  sensible window; far-future and long-past dates just show the date.
- Defined two CSS tokens that were referenced but missing (AI panel styling);
  guarded the last unvalidated persisted reads (updater last-check, search
  filter); added a score-grid shape check so contract drift fails loudly.
- Server: `fixtures/check` returns an honest 503 (not a 500) on a malformed
  upstream response; the fixture diff no longer walks the index row-by-row.

### Changed
- **Plainer language on the everyday screens.** Metric jargon is glossed on
  hover (ECE, RPS, log loss, Brier), "Elo · ordered logit" reads "Elo ratings",
  and betting/stats shorthand (`1X2`, "marginals", `−ln(p)`, `P(H/D/A)`) is
  reworded. Page titles now match their nav labels ("Backtests", "Track record").
- **Backtests is readable at a glance** — a summary strip of who leads how many
  folds, collapsible per-competition groups, glossed headers, and the leading
  model highlighted per fold. Every number is still shown.
- **A calmer, more tactile surface** — status and fact chips carry glyphs (not
  colour alone), a faint paper-grain texture and top-lit card edges add depth,
  and subtle reduced-motion-gated motion settles the seal stamp and drawers. The
  header now uses the static logo (the animated mark is reserved for the splash).
- Theme and reading controls are now reachable from **Settings › Appearance**, in
  addition to the header.
- Faster first paint: views are code-split and load on demand (initial JS ~193 KB,
  down from ~297 KB), GET requests are cached and de-duplicated within a session
  and cleared on any write, and the heavy heatmap/reliability charts are memoized.

### Added
- **A one-time welcome card** on the Games home — the three things Golavo does
  (open a match, seal before kickoff, track the score), dismissible and calm.
- **Retry buttons** on the model council and match notebook when the engine is
  still warming up, instead of a dead-end message.

### Docs & CI
- Overhauled the docs site and READMEs for the post-pivot app: rewrote the
  matchday page around the Games home and Match Cockpit, resynced the roadmap,
  reconciled the privacy/security page with `SECURITY.md`, corrected the
  architecture API surface, rewrote `ui/README.md`, refreshed the facts
  catalogue, and added the missing `match_analysis` contract schema.
- CI now compiles the Tauri desktop shell (`cargo check`) on every
  PR, uses `npm ci`, and runs the accessibility gate over ten routes (up from
  four) plus a mobile-popover regression test.

## [0.3.2] - 2026-07-12

AI mode grows up: a deeper, cited read of the commentator notes for any match —
with honest progress while the model works, and one-click access once configured.

### Added
- **AI Analyst Read on the Match Cockpit.** Any indexed match — not just sealed
  forecasts — can now get an optional AI synthesis of its Commentator's Notebook
  and model council. The AI is explicitly instructed to go **deeper than the
  page**: every claim must connect at least two pieces of evidence (fact ↔ fact,
  or fact ↔ council probability), surface tensions and corroborations, and say
  what remains unknown. It runs under exactly the sealed path's fail-closed
  guards — numeric whitelist, mandatory citations, betting-lexicon rejection —
  via a new match evidence bundle (`ma_*`, evidence schema 0.2.0) whose identity
  can never masquerade as a sealed forecast's. New endpoint
  `POST /api/v1/matches/{id}/narrative`.
- **A refresh that regenerates.** "Refresh read" skips the cache and asks the
  model again; the new output still passes every guard before a word is shown.
- **Honest progress while the model thinks.** An indeterminate progress bar, the
  factual pipeline stages, and an elapsed-seconds ticker with
  expectation-setting copy ("local models think at their own pace — a minute is
  normal; nothing shows until every number is verified"). Respects
  reduced-motion.
- **One-click AI toggle in the header** — shown only once a provider has been
  configured (Settings or an AI panel remain the explicit first-time opt-in).
  It flips the same persisted setting every AI panel reads, remembers the last
  provider, and stays in sync app-wide.

### Notes
- AI remains **off by default**, local-first, and additive: it cannot change a
  probability, and the deterministic analysis is complete without it. Verified
  end-to-end against a real request/response cycle: a grounded synthesis passes
  review; an output with one invented number is discarded to `local_only`.

## [0.3.1] - 2026-07-12

Sharper commentator notes and a cleaner post-pivot flow.

### Added
- **Signature form stats in the Commentator's Notebook** — the unusual insights a
  commentator knows but most scoreboards never show, all deterministic and
  number-disciplined:
  - **both-teams-scored rate** — how often a side's recent matches see both teams
    find the net;
  - **scoring momentum** — goals a game over the last six versus the stretch
    before, surfaced only when the shift is real;
  - **clean-sheet rate** — how reliably a defence shuts the door (distinct from the
    current clean-sheet streak);
  - **head-to-head goal character** — the average goals and both-scored count in
    the meetings, the dimension the win/draw/loss record leaves out.
  Registry version bumped; these run under the same pre-registered
  multiple-comparison, sample, and freshness guards as every other fact.

### Changed
- **"Three things to know" and the Commentator's Notebook no longer overlap.** The
  headline picks are removed from the full notebook below, so the notebook is the
  deeper cut rather than a repeat — the two panels now partition the facts.
- **Post-pivot link and label cleanup.** The sealed-forecast list is titled
  "Sealed forecasts" (under Model Lab); cross-links from the ledger, backtests, and
  forecast pages point at the new `/lab/*` routes instead of the retired
  `#/ledger` and `#/eval`.

## [0.3.0] - 2026-07-12

The architecture rethink, first slice: Golavo opens on **games**, not on an audit
form, and any match can be understood at an analyst level on demand. The sealing,
provenance, calibration, and no-leakage machinery is unchanged — it moved behind
the product, where it belongs.

### Added
- **Match Cockpit — a model council for any indexed match.** Opening a match now
  computes an on-demand, leak-safe multi-model read at the seal's own
  `kickoff − 1s` cutoff:
  - a **Replay** for a played match (reconstructed with pre-kickoff data only — it
    is *not* a forecast that existed at the time, and never enters the track
    record) or a **Preview** for a scheduled one, each labelled and time-stamped;
  - **two voices** — Elo (ratings) and Dixon–Coles (goals) — shown side by side
    with whether they agree, plus a climatology **baseline** for reference. The
    Poisson variants are disclosed, never counted as extra opinions, and nothing is
    averaged into a synthetic consensus;
  - model-implied goals (labelled *expected, not predicted*), the goal model's
    coherent exact-score grid, and an honest **abstain** state when either side has
    too little history.
  New endpoint `GET /api/v1/matches/{id}/analysis` (contract 0.3.0, additive).
- **Games-first home.** The default page is now **Games**: recent results and any
  upcoming fixtures from the local index, a search entry to 75,000+ matches, and
  league shortcuts. A fresh install with an empty ledger is a full, useful page —
  offline, no account. New endpoint `GET /api/v1/matches/recent`.
- **Leagues browse hub** for the five bundled club leagues and internationals.
- **Model Lab.** Track record, Backtests, Methodologies, and the sealed-forecast
  list are consolidated under one section. The new *Methodologies* page explains,
  in plain terms, why three of the five families are really one voice.

### Changed
- **Primary navigation is now Games / Leagues / Model Lab.** The old Matchday /
  Matches / Ledger / Evaluation tabs are gone; `#/ledger` and `#/eval` redirect
  into Model Lab so existing links and exports keep working.
- **Sealing is reframed as an expert "Track this prediction" action** — the cockpit
  is the live read; sealing is how you put a pre-kickoff prediction on the record.
  The seal engine, eligibility rules, and immutability are unchanged.

### Notes
- No fabricated capabilities: live club fixtures, standings, season projections,
  and observed xG/lineups/injuries are **not** part of this release (no lawful open
  source exists for the latter as of this writing). The Match Cockpit is honest
  about what it can and cannot show.

## [0.2.6] - 2026-07-12

### Added
- **Reading comfort** (header **Aa**). A small popover for how the app *reads* —
  never what it says: theme (Light, Dark, or a new **Warm** low-blue palette for
  evening reading), text size (four steps that scale the whole app), line spacing,
  and contrast (which follows the OS "increase contrast" setting). Warm is a
  dedicated, contrast-checked palette, not a screen tint. It's for comfort, not eye
  protection, and the copy says so.
- **"Three things to know" now leads with the fact closest to the fixture** — a
  head-to-head record surfaces above a competition-wide base rate (ranked by scope,
  then specificity). Still a pure, documented pick from the notebook; never AI.
- **"What moved" on a re-seal.** When a fixture is re-sealed, the newer forecast
  shows each outcome's probability *was → now* with the change in whole points —
  line movement between two honest pre-kickoff seals, not an edit, deltas summing
  to zero.
- **Activate local AI from Settings.** A new *Local intelligence* section surfaces
  the AI Deep Read provider (Off by default; Local · Ollama / llama.cpp, or
  OpenAI / Anthropic BYOK). It only reads and cites the sealed numbers and can never
  change a probability.
- **Automated UI gate.** A Playwright + axe-core suite checks no horizontal overflow
  at mobile/tablet/desktop widths and no serious accessibility violations across all
  three themes, on every push.

### Changed
- **Probabilities read as whole numbers** in the bars and plain-language summaries
  (rounded so a 1X2 split still sums to 100), with a natural-frequency gloss ("about
  3 in 5"); one decimal survives only in the expert tables.
- **The local engine prefers a refreshed data snapshot when one is present** —
  internal groundwork toward pulling a newly-spotted fixture in so it is instantly
  forecastable (no user-facing control yet).

### Fixed
- **Header settings gear** redrawn — the previous icon's transform left it visibly
  off-centre.
- **Settings spacing** — hint text now sits with its control and wraps at a readable
  measure instead of bleeding across the panel.
- **Probability-bar labels now clear WCAG AA 4.5:1 in every theme.** The light and
  warm palettes previously dropped the dark segment labels just under the threshold;
  the bar now uses theme-independent segment colours.

## [0.2.5] - 2026-07-12

### Added
- **Redesigned match & forecast pages** — a calmer "workbench" layout: a unified
  match header, a single trust strip, plain-language insight cards, and expert
  detail tucked into collapsible drawers. Same sealed numbers, presentation only,
  now with a UI test suite (Vitest).
- **Opt-in "keep fixtures up to date"** (Settings → Data, off by default). When
  on, Golavo asks the CC0 fixture source on launch whether a new upcoming
  international match has appeared, and flags it on the Matches page. This is the
  **only** time the app reaches the network on its own — it reads only public
  fixture data and sends nothing. New read-only `GET /api/v1/fixtures/check`.

### Changed
- **Search remembers where you were.** The query, filters, and results survive
  opening a match and pressing Back (persisted in sessionStorage, not the URL),
  the empty state offers popular-search chips so the directory is browseable
  without typing, and the warming / error / load-more states now offer Retry.
- **The sidecar launch token is passed via the environment, not the command
  line**, so it is no longer visible to other local processes via `ps`; the
  sidecar also refuses to bind a non-loopback host. Verified end-to-end on a real
  desktop build — the auth gate enforces the env-delivered token.

### Fixed
- **SECURITY.md corrected in both directions.** In-app updates are cryptographically
  signed and verified against a pinned public key (not "planned/gated on secrets");
  and the claimed logging-redaction filter, backup/verify migrations layer, and
  local crash reporting were removed — none of those mechanisms exist. The
  deterministic fact engine is no longer listed as planned.

## [0.2.4] - 2026-07-12

### Added
- **Generate a forecast from inside the app — no CLI.** A new write route
  `POST /api/v1/matches/{match_id}/seal` runs the same deterministic engine as
  `golavo seal` (byte-identical) and persists an immutable artifact; `GET
  /api/v1/matches/{match_id}` now carries a typed `seal_eligibility` verdict. The
  match page shows a **Generate local forecast** button for an eligible fixture,
  and an honest, reason-specific message otherwise (already played, seal window
  closed, internationals-only, pack unavailable). Forward seals cover men's senior
  internationals — the only source that maps to one pinned CC0 pack. The client
  supplies only a match id and optional model family; the pack, training date, and
  as-of are all resolved server-side, so a seal cannot be backdated or pointed at
  an untrusted pack. Idempotent per (fixture, family), and it runs off the event
  loop so a slow seal never freezes the rest of the API. **The desktop build now
  bundles the internationals pack**, so sealing works in the installed app — the
  `--smoke` probe fails the build if the pack is missing.
- **Outcome & goal summaries on the forecast page.** Exact re-buckets of the
  sealed score distribution — double chance, total-goal thresholds, and the
  total-goals distribution — computed as true marginals of the same grid, so they
  reconcile with the 1X2 and score numbers by construction. Analysis language
  only; markets whose tail isn't exactly recoverable (both-teams-to-score, clean
  sheets, per-team totals) are deliberately omitted.
- **Match Search + a Commentator's Notebook for any game.** A new read-only search
  surface over a committed, deterministic Parquet index of **75,079 matches**
  (**49,505 internationals** from martj42 + **25,574 club** from the five openfootball
  leagues — EPL, La Liga, Bundesliga, Serie A, Ligue 1), built by
  `python -m golavo_core index`. Four GET, token-gated, read-only endpoints:
  `GET /api/v1/matches/search` (`q` < 2 chars → 422; index missing → 503;
  `status` ∈ `played|upcoming` derived from `is_complete`, never a midnight-UTC
  day-proxy kickoff), `/matches/competitions`, `/matches/{id}`
  (`linked_by: "match_id"|"fixture"|null`), and `/matches/{id}/notebook`.
  - **A Commentator's Notebook for *any* searched match.** A match without a precomputed
    notebook gets one computed **on demand** at `as_of = kickoff − 1s` — the same
    conservative horizon `seal_forecast` uses — so it can never read the fixture's own
    result or any later match (leak-safe; tested and confirmed on the real index). A
    sealed match with a precomputed notebook serves that instead
    (`computed: "precomputed"` vs `"on_demand"`). This is the one deliberate tradeoff:
    the sidecar now reads the frozen index at runtime, but it stays read-only in the
    write sense (`build_notebook` writes nothing; the facts no-write invariant is
    AST-enforced), the engine still owns every number, and the precomputed
    `/forecasts/{id}/facts` path is untouched.
  - **Sample forecasts can never masquerade as real seals.** Match ↔ forecast linking
    scans the **real ledger only** (`ARTIFACT_DIR`), by `match_id` then a
    `(date, home, away)` fallback, so a synthetic sample id can never attach to a real
    match. Linking is cheap navigation (no integrity check); the forecast route still
    recomputes each artifact's content-addressed identity on serve.
  - **License gate — ODbL can never ship in the sidecar.** The index builder fails closed
    unless every source pack is `CC0-1.0`, and both `check_license_isolation.sh` and CI
    assert the committed index's `built_from` licenses are all CC0. Per-pack `match_id`s
    are preserved across the merge (never re-hashed over the combined frame), a
    cross-pack collision aborts the build, and CI rebuilds the index and asserts
    byte-equality with the committed copy (`parquet_sha256`) — a drift means "rebuild +
    recommit". The frozen index + side tables (~2.4 MB) are bundled into the desktop
    sidecar.
  - **UI:** a `/matches` search view (debounced, grouped internationals/club, filters,
    honest badge states incl. "Result not in snapshot") and a `/match/{id}` detail with
    four forecast states (sealed → link; played → "Golavo never retro-forecasts a played
    match"; future → "sealing from inside the app lands in a future release", club-gated
    to note historical-backtest-only; not-found → search) plus an always-on Commentator's
    Notebook block. Nav entry, header search icon, and a sample-banner CTA.
    **Seal-from-UI is deferred — the API stays all-GET.**
  - **Quick wins:** Matchday + Ledger client-side filters; an AI Deep Read sample-mode
    note; Eval ↔ Ledger cross-links; a Settings footer link; not-found → search.
  - Known gap: the vendored packs are historical, so `status=upcoming` (an unplayed
    fixture kicking off today or later) is **empty until a pack refresh** adds
    scheduled fixtures — likewise, in-app sealing has nothing in-window to seal
    until then, and reports a typed `kickoff_passed`/`pack`-scoped reason honestly.
  - See [`docs/handoff/match-search.md`](docs/handoff/match-search.md).

### Fixed
- **Search: multi-word queries and match-day fixtures.** Search now tokenizes the
  query and requires every term to appear (in either team name or the
  competition), so "argentina switzerland" resolves to that fixture instead of
  returning nothing; multi-word former-name aliases (e.g. "soviet union" → Russia)
  still resolve. `status=upcoming` now measures from the start of today (UTC)
  rather than `now`, so a fixture stays listed through its own match day instead
  of vanishing at the midnight-UTC day-proxy kickoff.
- **Ledger writes are crash-safe.** Artifacts are written atomically (temp file +
  rename) under a lock, a truncated file left by a killed process is repaired
  rather than permanently blocking that fixture's id, and scoring/voiding now
  integrity-verify the input seal before writing a successor.
- **Frozen sidecar: on-demand Commentator's Notebooks were always empty (desktop
  regression in 0.2.3).** The PyInstaller spec bundled only three of the four
  runtime contract schemas — `docs/contracts/facts.schema.json` was missing — so
  in the installed app `build_notebook(validate=True)` raised on the schema read
  and `GET /api/v1/matches/{id}/notebook` failed closed to `available: false`
  for every match without a precomputed notebook. Source mode was unaffected,
  which is why tests and dev runs never saw it. Three-layer fix: the spec now
  bundles `facts.schema.json`; the sidecar `--smoke` probe additionally requests
  one real on-demand notebook and fails unless `available: true` (so a dropped
  `docs/contracts` datas entry fails CI's sidecar-smoke job instead of
  shipping); and a unit test asserts every `*schema_path` resolver target in
  `golavo_core.resources` is listed in the spec datas, catching the omission at
  PR time in source mode.

## [0.2.3] - 2026-07-11

### Added
- **Entertaining startup screen.** The loading splash now shows a live progress
  bar with a status line ("Unpacking the forecasting engine…" → "Warming up the
  models…" → "Almost ready…") and a rotating deck of genuinely-true, genuinely-
  obscure football facts, so the ~30-40s first-launch unpack passes with
  something to read instead of a bare spinner. The progress bar eases toward
  ~94% and lets the app itself take over the moment the engine is ready — it
  never claims to be finished before it is. Both themes, reduced-motion aware.

## [0.2.2] - 2026-07-11

**Desktop first-run UX fixes.** Two problems a fresh desktop install hit:
a ~30-40s blank window while the engine unpacked (felt broken, no feedback),
and an empty Matchday (the sidecar read the empty per-user ledger instead of
showing anything).

### Fixed
- **Instant window + honest loading state.** The window now opens
  **immediately** with a "Starting the local engine…" splash instead of
  ~30-40s of blank screen — the health gate moved off the main thread and the
  UI holds behind the splash until a `backend://ready` signal (or a `/health`
  poll). Time-to-window measured ~2-3s (was ~45s).
- **Sample forecasts on a fresh install.** The desktop app now **shows the 8
  bundled synthetic sample forecasts** when the ledger is empty, labelled
  honestly — a "Sample data" badge and a first-run banner, driven by a new
  `GET /api/v1/meta` (`forecast_source: sample|ledger`). Samples never reach
  the forward calibration record (that always reads the real ledger), a lone
  corrupt seal no longer blanks Matchday, and the post-update "Updated to X"
  toast is re-checked after the (now background-thread) finalize so it isn't
  missed. The badge stays neutral until the source resolves rather than
  flashing "Live" over synthetic data.

Two independent review loops (four adversarial passes) ran over this change;
all findings closed and verified before release.

## [0.2.1] - 2026-07-11

**First updater-enabled release.** Installs of v0.2.1 and later update themselves
in-app (consent-first, signature-verified, ledger backed up before install).
v0.1.0 and v0.2.0 predate the updater — update from them with one manual
download; it's in-app from then on. macOS fatal-launch dialog now blocks via
osascript (the pre-event-loop rfd path flashed and orphaned the window); two
adversarial review loops plus an install/no-crash verification hardened the
whole flow.

### Fixed
- Harden the read-only forecast list against a schema-broken artifact on disk: a
  `jsonschema.ValidationError` (not a `ValueError`) is now caught alongside the
  other bad-artifact errors, so one corrupt `fa_*.json` is omitted rather than
  failing the whole `/api/v1/forecasts` request. Follow-up to H1.
- **Windows sidecar watchdog: pinned-handle rewrite (extends v0.2.0's H3).**
  The `--parent-pid` probe's `os.kill(pid, 0)` was worse than H3 described:
  CPython maps signal 0 through to `TerminateProcess`, so the probe KILLED the
  desktop shell ~1s after boot rather than merely erroring. This replaces the
  H3 probe with a test-covered implementation: `OpenProcess` + zero-timeout
  wait, a pinned parent handle on Windows (immune to PID reuse), probe errors
  treated as parent-gone, and unit tests for both platform branches.

### Added
- **In-app updates (desktop).** Golavo now updates itself — no git, no
  terminal. Consent-first: a one-time card asks before any update check ever
  leaves the machine (the "no runtime network call unless you opt in" promise
  holds); enabled, the app checks GitHub once a day and shortly after launch.
  The flow is staged and explicit — passive header pill → Software Update
  sheet (release notes, **Update now** / **Skip this version** / **Later**) →
  event-driven progress bar with a working Cancel → platform-true install
  ("Restart Golavo" on macOS, "Quit & install" on Windows, which reopens
  itself). Every download is **cryptographically verified** against the
  public key compiled into the app before installing (the updater keypair now
  exists; CI signs every release artifact). The ledger is backed up
  immediately before install, and the backup has a real lifecycle: armed only
  until the new version's first healthy boot (then retired), restored with a
  native explanation dialog if that boot fails — never restorable twice, and
  never months later over newer data. A new **Settings** page (header gear)
  shows the version, auto-check toggle, last-checked time, manual **Check
  now**, skip management, and the record of the last verified update; the
  post-update toast only claims "ledger backed up" when one truly was.
  Source/dev builds show honest "update via git / releases" copy instead of
  dead controls. New sidecar route `POST /api/v1/shutdown` (token-gated,
  desktop-only) lets the shell stop the whole sidecar tree before the Windows
  installer runs. Local E2E harness: `scripts/test-updater-local.sh`.

### Changed
- **Release pipeline hardened for updates.** Stable `v*` releases now publish
  as real (non-pre-) releases so the update endpoint resolves; the release is
  a draft until every asset — installers, signatures, and the new
  `latest.json` update manifest — is uploaded, then flips live atomically.
  The manifest uses installer-specific Windows keys (`windows-x86_64-nsis` /
  `-msi`) so an MSI install is never "updated" by the NSIS installer. CI
  hard-fails a tag whose version doesn't match the committed one
  (`make release-bump VERSION=x.y.z` syncs all 11 spots via
  `scripts/bump_version.py`), a stable tag without the signing secret, a
  placeholder pubkey, and a half-built platform matrix.

## [0.2.0] - 2026-07-11

**Hardening capstone.** An adversarial self-review of the shipped v0.1.0 product
(see [`docs/handoff/v0.2-review.md`](docs/handoff/v0.2-review.md)) found **no
Critical** defects and **three High** findings — each fixed below with a
regression test. Determinism, the AI numeric whitelist, key isolation, and the
model coherence guarantees held under scrutiny. This release also folds in the
Phase 7–8 work (Fact & Coincidence engine; exact-score matrix + Casual/Expert)
that accumulated after the v0.1.0 tag.

### Security
- **Artifact integrity is now verified on every read path (H1).** The read-only
  API and the calibration aggregator recompute each artifact's `payload_sha256`
  and content-addressed `artifact_id` before use (`verify_artifact_integrity` /
  `load_verified_artifact`), not just schema + coherence. A hand-edited or swapped
  `fa_*.json` is omitted from the forecast list and refused (HTTP 500) on direct
  fetch, and can no longer skew the public calibration record. Previously the serve
  path trusted on-disk JSON, so the "coherence enforced on every load / immutable,
  auditable" guarantee held only on the write path.
- **Pack-integrity claims corrected to match the code (H2).** `SECURITY.md`,
  `packs/README.md`, and `README.md` described data/model packs as **minisign
  signature-verified against a pinned public key** with an "unsigned packs require
  override" control — none of which exists (only per-file SHA-256 self-hashing).
  Reworded to the true mechanism (hash-verified corruption-detection) and marked
  signature verification **planned (ADR-0001), not yet implemented**. The release
  workflow's checksum-"signing" step was a no-op `echo` that still flipped a keyed
  release to a full (trusted-looking) release; it now fails loudly when a key is
  set (signing is unimplemented), and the notes no longer imply `SHA256SUMS.txt`
  authenticates a download.

### Fixed
- **Desktop sidecar no longer orphans on Windows (H3).** The parent-death watcher
  used POSIX-only semantics: `os.kill(pid, 0)` is a harmless probe only on POSIX
  (on Windows it routes through `GenerateConsoleCtrlEvent`/`TerminateProcess` and
  raised an uncaught `OSError`), and orphan reparent-detection never fires there.
  On the shipped Windows target the sidecar leaked on `127.0.0.1` every session.
  The watcher now dispatches by platform — a non-destructive
  `OpenProcess`/`WaitForSingleObject` liveness probe on Windows, the signal-0 probe
  on POSIX — with the reparent heuristic disabled where it is meaningless.

### Changed
- Version bumped to **0.2.0** across core/server (`pyproject.toml`, `__version__`),
  `ui`/`desktop`/`docs-site` `package.json`, `tauri.conf.json`, and `CITATION.cff`;
  the `docs-site` manifest is corrected from a stray `0.0.0`. Contract
  `schema_version` constants are deliberately unchanged.

### Docs
- Added the severity-ranked adversarial review
  ([`docs/handoff/v0.2-review.md`](docs/handoff/v0.2-review.md)) and the release
  handoff ([`docs/handoff/codex-v0.2.md`](docs/handoff/codex-v0.2.md)); corrected
  the stale reviewer dossier `docs/reviews/codex-review-prompt.md` (it still
  described "Phase 0, no engine yet") to the shipped state, and `SECURITY.md`'s
  stale "Phase 0 has no updater" line. Deferred Medium/Low findings are tracked in
  the review's TODO list.

### Added
- **Phase 8 — Exact-score distribution + Casual/Expert presentation.** Goal-based
  families (independent / Dixon-Coles / bivariate Poisson) now seal the
  exact-score distribution the 1X2 forecast already implied, as an additive
  `forecast.score_matrix`: a display grid of concrete scorelines `0..7` per side
  plus an outcome-decomposed `8+` tail bucket. The sealed probabilities, expected
  goals, and grid are all derived from **one** matrix (integrated to 20 goals/
  side), so they are coherent by shared source. A **machine-checked coherence
  invariant** enforces it: `validate_artifact` reproduces win/draw/loss from
  `grid + tail` on every load (rejecting any incoherent matrix), and `seal_forecast`
  additionally proves the matrix mean reproduces `expected_goals` before writing —
  an incoherent matrix aborts the seal rather than being shown. Goal-less families
  (climatological / Elo) and abstained seals carry **no** matrix: an honest
  "no exact-score distribution" state, never a fabricated grid. The schema bumps
  additively within `0.2.0` (existing `0.1.0`/`0.2.0` artifacts still validate);
  sample fixtures regenerated coherently. The AI evidence bundle gains the top-3
  scorelines and the tail as whitelisted `allowed_numbers`, so the AI may cite
  e.g. "most likely 1-1 at 12.6%" — the numeric whitelist still governs, so it
  cannot invent a scoreline or a percentage. A new **Casual ⇄ Expert** toggle
  presents the same sealed numbers at two depths (the toggle never changes
  displayed certainty): Casual = verdict bar + a band-generated plain-language
  summary (not AI) + cited sealed-number facts; Expert = an accessible score-matrix
  heatmap (table semantics, most-likely highlighted, theme-aware, reduced-motion
  safe) with the tail, the model's spread, versions, and calibration context.
- **Phase 7 — Fact & Coincidence engine (the Commentator's Notebook).** A new,
  deterministic `golavo_core.facts` package computes source-backed match facts
  over the vendored CC0 packs. A fixed, pre-registered family of templates
  (`family_size` = 26 hypotheses/match — the multiple-comparison bound) emits
  facts each labelled **predictive / context / coincidence** and carrying its
  sample, denominator, base rate, source ids, and freshness. Guardrails: per-
  template minimum-sample suppression, staleness auto-hide, and a coincidence cap
  (≤3, ranked by specificity not significance) with UI quarantine. Every fact's
  text is number-disciplined, so context/predictive facts fold verbatim into the
  AI evidence bundle's numeric whitelist (coincidences never do). Internationals-
  only scorer/shootout facts; no club scorer/lineup data is fabricated; the
  promoted-team rate is an honest debut-window proxy. A **machine-checked
  no-write invariant** (static import isolation + runtime immutability) proves no
  fact code path can change a probability, forecast, or calibration number.
- Read-only `GET /api/v1/forecasts/{id}/facts` serving a precomputed notebook; a
  `golavo notebook` CLI command; a UI **Commentator's Notebook** panel; and an
  additive `facts.schema.json`. `build_evidence_bundle` gains additive
  `extra_facts`/`extra_numbers` params (default output byte-identical).

## [0.1.0] - 2026-07-11

First tagged release — an **unsigned pre-release**. The source, the deterministic
engine, the optional off-by-default AI layer, and the docs are complete and
tested; the desktop bundles build **unsigned**, so macOS Gatekeeper and Windows
SmartScreen warn on first launch. Code signing, notarization, and the signed
auto-updater are wired but **gated on secrets that are not configured**, so no
signed or notarized artifact is produced or claimed. The calibration record ships
**empty** and only ever accumulates genuine pre-kickoff seals.

### Added
- Phase 6 release hardening. A whole-repo claims/honesty audit
  (`docs/handoff/phase6-claims-audit.md`) reconciled every capability claim with
  shipped, tested code at the release commit. One deterministic end-to-end
  integration test (`server/tests/test_phase6_e2e.py`) composes the whole
  pipeline — provenance-validate packs → ingest → evaluate a fold → forward-seal
  a scheduled fixture on snapshot T0 → score it from T1 → aggregate the
  calibration record → build the evidence bundle → run the AI narration path with
  a **canned adversarial** response and assert the numeric whitelist falls back to
  local-only — with byte-stable artifacts and **no network, no live LLM**.
  Per-competition **model cards** with the real backtest metrics and reliability
  diagrams are generated from the evaluation artifacts by
  `scripts/build_model_cards.py` (never hand-typed). **Authentic screenshots** of
  the running v0.1.0 workbench — matchday, sealed/scored, the calibration record,
  and the AI Deep Read panel OFF and ON — captured over the clearly-labelled
  synthetic sample artifacts and surfaced on the landing page and README. Coherent
  `0.1.0` versioning across `core`/`server`, `ui`, `CITATION.cff`, and the Tauri
  config.
- Phase 5 optional, local-first **AI Deep Read** — off by default and strictly
  additive; the whole app works identically with AI disabled. The deterministic
  engine owns every probability; the AI only explains and cites, and is
  structurally prevented from stating any number the engine did not produce. It
  **does not improve accuracy** and cannot change a probability.
  - `MatchEvidenceBundle` (`golavo_core.evidence`, additive schema
    `evidence_bundle.schema.json` 0.1.0): a pure function of a sealed/scored
    artifact carrying an explicit `allowed_numbers` whitelist — every numeric
    value the AI may utter, each with an id, unit, display string, and citable
    source.
  - AI guards (`golavo_core.ai`, network-free): an exact-display, reference- and
    unit-bound, unicode-safe numeric whitelist matcher; narration review
    that strips chain-of-thought, drops uncited claims, and hard-rejects
    unsupported numbers, betting lexicon, and credential-shaped content;
    an untrusted-text sanitizer; and a fixed, versioned system prompt. Forced
    structured output via `ai_narration.schema.json` 0.1.0.
  - AI gateway (`golavo_server.ai_gateway`), the only module that talks to an
    LLM: OpenAI-compatible (Ollama / llama.cpp) and BYOK OpenAI/Anthropic over
    stdlib `urllib`; injected transport for CI; parse → review → one retry →
    local-only fallback; cache keyed by every prompt-affecting input; keys from
    env/keychain, header-only, never logged.
  - `POST /api/v1/forecasts/{id}/narrative`: additive, off by default; returns a
    guard-validated narration or an explicit off/unavailable/local-only state.
    The read-only forecast surface is unchanged; AI never blocks a forecast.
  - UI "AI Deep Read" panel: off-by-default provider selector, subordinate to the
    sealed numbers, cited claims with source + number chips, factual pipeline
    stages only (never model reasoning), honest fallback states.
  - CI red-team suite (no live LLM): adversarial bundles/responses that try to
    change a probability, fabricate a number/citation, smuggle betting language,
    leak chain-of-thought, or exfiltrate a key — all fail closed to local-only.
  - Post-handoff hardening binds every numeric token to the exact display and id
    referenced by its claim, rejects ambiguous numeric notation, constrains local
    model endpoints to loopback, forbids cloud base-URL overrides, keys caches by
    all prompt-affecting inputs, and invalidates stale UI requests on provider or
    artifact changes.
- Phase 4 desktop app: a Tauri 2 shell that packages the FastAPI core as a
  PyInstaller **onefile sidecar** (`golavo-sidecar-<target-triple>`). On launch it
  picks a free `127.0.0.1` port, mints a per-launch token, spawns the sidecar,
  waits for `/health`, then shows the workbench with `window.__GOLAVO_RUNTIME__`
  injected so the UI talks to the ephemeral port + token (nothing hardcoded); on
  quit it kills the sidecar. A frozen-vs-source resource resolver
  (`golavo_core.resources`) finds the bundled schema/eval summaries under
  `sys._MEIPASS`. The read-only API gains an `x-golavo-token` gate on `/api/*`
  (open in source mode; `/health` + CORS preflight exempt) and Tauri CORS origins.
- Orphan-proof sidecar lifecycle: the sidecar watches the shell pid
  (`--parent-pid`) and self-exits if orphaned — needed because the onefile
  bootloader forks a Python child the shell's kill can't reach directly.
- Packaging + CI: `packaging/build.sh` and `packaging/golavo-sidecar.spec` produce
  unsigned `.dmg` (macOS) and `.msi`/`.exe` (Windows) with `SHA256SUMS`;
  `release.yml` builds them on native runners; `ci.yml` gains a frozen-bundle
  `--smoke` job on macOS + Windows. Signing/notarization and the signed
  auto-updater (pre-update backup + health check + rollback) are wired but
  **gated on secrets** (`TAURI_SIGNING_PRIVATE_KEY`, `APPLE_*`), never fabricated.
- Phase 3 forward sealed-forecast loop (internationals only): seal a genuinely scheduled
  fixture before its conservative day-proxy kickoff (the source has dates, not kickoff
  times), score it from a strictly newer retained snapshot, or void it with a recorded
  reason on postponement/abandonment — the seal's bytes never change.
- Snapshot retention: `build_sourcepack.py` is parameterized by pinned upstream ref,
  output directory, and file set; snapshots are immutable, never re-fetched, and
  registered in the new `packs/snapshots.json`; `validate_provenance.py` discovers every
  pack and cross-checks the registry. A second retained internationals snapshot
  (`273c731492df…`, in which France–Morocco 2026-07-09 is still scheduled) makes the
  seal→score loop replay deterministically in CI against the Phase 0 pack's completed
  result.
- Data-state anchoring: new-pack manifests record `upstream_committed_at_utc` (the pinned
  ref's public commit time) next to the honest `retrieved_at_utc`; seal and score
  validity are checked against the anchor, with retrieval time as the fallback for
  packs built before the anchor existed.
- ForecastArtifact contract 0.2.0 (additive over 0.1.0): optional
  `Snapshot.upstream_committed_at_utc`, optional top-level `void_reason`, shared
  ActualResult/ScoreMetrics defs, and the new CalibrationSummary contract; `golavo void`
  CLI command with a mandatory reason.
- Real calibration record: `golavo_core.calibration` aggregates the immutable ledger's
  sealed→scored/voided chains (one resolution per seal, reconciled counts, running log
  loss/Brier, reliability bins) — never backtests; served read-only at
  `GET /api/v1/calibration` and rendered in the workbench's new Ledger view, clearly
  separated from the evaluation folds.
- Phase 2 club coverage: pinned `openfootball` sourcepacks (CC0-1.0, same upstream ref as
  Phase 1) for La Liga, Bundesliga, Serie A, and Ligue 1 — historical completed seasons
  only, one independently modeled pack per league (no cross-league strength calibration).
  The audit gate is league-aware (expected matches derived from actual team count, checked
  against each league's constitutional size) and excludes, honestly: La Liga & Serie A
  2024-25 (final matchday missing at capture), Ligue 1 2019-20 (COVID abandonment), and
  every league's partial 2025-26 capture.
- Evidence-based team-name canonicalization for es/de/it/fr with a machine-checked proof
  (`scripts/check_team_fragmentation.py`, `docs/handoff/team-canonicalization.md`):
  within-season injectivity, cross-season drift merged, distinct clubs kept distinct.
- Per-league chronological season-fold evaluations (three most recent clean seasons each);
  the combined evaluation API and workbench now surface all five leagues' folds.
- Phase 1 club coverage: pinned `openfootball` English Premier League sourcepack (CC0-1.0)
  gated by a coverage audit (`docs/handoff/openfootball-audit.md`) that accepts 15 clean
  completed seasons (2010-11 → 2024-25) and excludes the partial 2025-26 capture.
- Source-agnostic ingestion (`load_matches` dispatcher) and chronological EPL season-fold
  evaluation reusing the five candidates; `evaluate-club` CLI; combined evaluation API.
- Phase 0 pinned martj42 internationals sourcepack with byte-level provenance validation.
- Deterministic climatological, Elo ordinal-logit, independent Poisson, Dixon-Coles,
  and bivariate-Poisson candidates with chronological WC2022/EURO2024/WC2026 evaluation.
- ForecastArtifact schema 0.1.0, immutable seal/score CLI, sample artifacts, and read-only API routes.
- EvalSummary `fold_id` widened from a fixed enum to a pattern (backward-compatible; admits club folds).
- Initial repository scaffold: README, Apache-2.0 license,
  animated brand marks, contributing/security/conduct policies.
- CI/CD workflows: continuous integration, signed release pipeline (stable + beta),
  and GitHub Pages docs deployment.
- Astro + Starlight documentation site scaffold.
- Package skeletons: `core/` (modeling library), `server/` (FastAPI + `/health`),
  `ui/` (React + Vite), plus `desktop/`, `packaging/`, and `packs/` placeholders.
- ADR-0001: desktop architecture decision (Tauri 2 + FastAPI/Python sidecar).

[Unreleased]: https://github.com/udhawan97/Golavo/compare/v0.14.1...HEAD
[0.14.1]: https://github.com/udhawan97/Golavo/compare/v0.14.0...v0.14.1
[0.14.0]: https://github.com/udhawan97/Golavo/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/udhawan97/Golavo/compare/v0.12.0...v0.13.0
[0.12.0]: https://github.com/udhawan97/Golavo/compare/v0.11.1...v0.12.0
[0.11.1]: https://github.com/udhawan97/Golavo/compare/v0.10.3...v0.11.1
[0.10.3]: https://github.com/udhawan97/Golavo/compare/v0.10.2...v0.10.3
[0.10.2]: https://github.com/udhawan97/Golavo/compare/v0.10.0...v0.10.2
[0.4.0]: https://github.com/udhawan97/Golavo/compare/v0.3.3...v0.4.0
[0.3.3]: https://github.com/udhawan97/Golavo/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/udhawan97/Golavo/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/udhawan97/Golavo/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/udhawan97/Golavo/compare/v0.2.6...v0.3.0
[0.2.6]: https://github.com/udhawan97/Golavo/compare/v0.2.5...v0.2.6
[0.2.5]: https://github.com/udhawan97/Golavo/compare/v0.2.4...v0.2.5
[0.2.4]: https://github.com/udhawan97/Golavo/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/udhawan97/Golavo/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/udhawan97/Golavo/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/udhawan97/Golavo/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/udhawan97/Golavo/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/udhawan97/Golavo/releases/tag/v0.1.0
