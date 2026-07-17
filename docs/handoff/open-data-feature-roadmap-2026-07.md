# Open-data feature roadmap — verified 2026-07-16

**Status: PLAN ONLY — nothing here is implemented.**

**Method:** two-loop verification. Loop 1: a codebase map of every extension point
(sources registry, fact registry, capability table, refresh allowlist, overlay
isolation, research policy) plus a fresh primary-source license/freshness sweep of
the open-data landscape. Loop 2: adversarial re-verification — every feasibility
claim checked against actual code (file:line) and every source claim checked against
live primary pages/APIs. Only items that survived both loops at **medium-high or
high confidence** are listed. This extends, and where dated supersedes,
`docs/handoff/expansion-plan.md` (2026-07-12) and
`docs/research/free-open-data-sources.md` (2026-07-10).

**Context that shapes the ranking:** after the WC final (Jul 19) every indexed
fixture is complete — the forward-seal lane goes dark (verified: upcoming fixtures
come solely from `openfootball/worldcup.json`; `refresh_sources.py` approves no
other fixture source). Meanwhile all five top-league **2026-27 fixture lists are now
published, complete, and CC0** on openfootball (verified match-by-match counts).
The app's forward life pivots to the domestic season, and the roadmap is sequenced
around that.

---

## Tier 1 — HIGH confidence

### 1. Unlock the 2026-27 domestic season (the big one)

- **Feature:** live standings, the already-built 10,000-run season outlook
  (P(title/top-4/relegation) per voice), schedule difficulty, and a year-round Games
  home matchday feed for EPL / La Liga / Bundesliga / Serie A / Ligue 1. Club score
  picks already work end-to-end (verified: `picks.py` has no source_kind gate and
  refreshed results settle picks automatically) — this turns My Season into a real
  season-long game in August.
- **Data:** openfootball 2026-27 Football.TXT fixtures, **CC0**, verified complete:
  England 380/38 MD (Aug 21–May 30), Germany 306/34, Spain 380/38, Italy 380/38,
  France 306/34 (in `openfootball/europe` — there is no standalone france repo).
  Weekly auto-update bot active (July 2026 commits).
- **What's already built:** the whole season engine — `certify_schedule()`
  double-round-robin certificate, standings rules verified against 2023-24,
  outlook, tie-breaks (`core/golavo_core/season_outlook.py`).
- **Real work found by loop 2:** the UEFA Football.TXT parser is **not** reusable
  (filename regex, `(ENG)` country-code tokens, `▪` stage markers, hardcoded
  `source_id`) — a domestic .txt fixtures parser is new code; the domestic
  `simulation` capability in `competitions.py:112-117` is a static literal that
  must be wired to the certificate; `refresh_sources.py _CONFIG` needs the new
  repos. Pick-void-on-postponement fragility (date-keyed match ids) worth a
  targeted fix.
- **Why high:** engine built, data verified complete and CC0, parser precedent
  in-repo. Natural deadline: La Liga opens Aug 16.

### 2. Women's World Cup history — data already on disk

- **Feature:** women's WC pedigree/awards facts and history surfaces (1991–2019,
  8 tournaments) beside the men's, era-badged.
- **Data:** already bundled — `packs/fjelstul-worldcup-f942c6b` CSVs contain the
  women's tournament rows (verified in tournaments/standings/appearances/awards).
  CC-BY-SA isolation is already live.
- **Real work:** `facts/wc_history.py:53-56` filters to "Men's World Cup" and
  cascades men's-only ids everywhere — remove the filter, add women's fact
  families + surfaces. No new license, no new pack, no new download.

### 3. Scorers & shootouts deepening (internationals)

- **Feature:** a scorers surface — tournament top scorers, per-player scoring
  timelines, goal-timing profiles, penalty/shootout ledgers — plus new fact
  families. First-class player-level content from data the app already ships.
- **Data:** `goalscorers.csv` + `shootouts.csv` already ingested as side tables
  (`match_index.py _write_side_tables`) and already cited by 7 fact families;
  goalscorers.csv verified updated through the current WC (Jul 15 commits).
- **Real work:** new fact families (registry-version bump, multiple-comparison
  budget widens — a reviewed change), a browse surface. Internationals-only
  (side tables ship only for martj42 — correct).

### 4. "Golavo Ratings" — in-house Elo for national teams

- **Feature:** as-of-dated Elo trajectories and a ratings table for national
  teams, replayable at any cutoff (fits sealing/leak-safe model), honest
  confidence notes. This is the lawful answer to the FIFA-ranking gap — verified:
  **no lawful free/open FIFA-ranking source exists** (eloratings.net unlicensed,
  mirrors are laundering), so computing our own from CC0 results is the only clean
  route, and it is fully redistributable.
- **What's already built:** Elo math in `models/candidates.py`
  (EloOrdinalLogitModel); month-end checkpoint re-fit pattern in
  `analytics.py _strength_trends`.
- **Real work found by loop 2:** the model keeps only final ratings — a
  trajectory emitter is new code, and trends today are per-competition; a
  cross-competition national-team scope is a deliberate (documented) choice.

### 5. Frauen-Bundesliga in the OpenLigaDB overlay

- **Feature:** first women's club coverage — display-only overlay context, same
  honest boundary as bl1/bl2/bl3/dfb.
- **Data:** verified populated: shortcut `fbl1`, season 2025 (2025-26), 182/182
  matches finished. ODbL, same license as the existing overlay — zero new legal
  cost. (2026-27 shortcut exists but is essentially empty so far.)
- **Real work found by loop 2:** shortcuts are hardcoded in
  `openligadb_source.py` (COMPETITION_SHORTCUTS, name prefixes, and three URL
  regexes embedding `bl1|bl2|bl3|dfb`) as well as `packs/overlay-odbl/policy.json`
  — a code+policy change, small but not policy-only.

---

## Tier 2 — MEDIUM-HIGH confidence

### 6. Women's internationals as a core dataset

- **Feature:** women's national-team browse, cockpit replays, backtests, facts —
  a whole new audience on the identical pipeline.
- **Data:** `martj42/womens-international-results` (~11k matches, active
  Jun 2026). **License nuance found by loop 2:** the GitHub repo has NO license
  file; the author's own Kaggle distribution of the same data declares **CC0**
  (verified in page JSON-LD, same author, same date). Defensible if pinned/cited
  from the Kaggle CC0 distribution; cleanest is asking upstream for a LICENSE file.
- **Real work:** known seams verified: `side_source` single-pack overwrite in
  `match_index.py:340-366` (second martj42 pack's side tables would be dropped),
  app-wide `team_category: "mens-senior"` declaration + seal copy, search can't
  distinguish men's/women's except by competition. Dataset self-describes missing
  friendlies — existing honest-gap machinery handles it.
- **Why not high:** license grant lives on Kaggle rather than the repo; known
  incompleteness.

### 7. Kickoff weather via Open-Meteo (display-only context)

- **Feature:** fill the Conditions Snapshot weather slot for upcoming matches
  with a true pre-kickoff forecast (issued_at recorded before kickoff — leak-safe
  by construction), per-user consent-gated fetch; historical stays blocked or
  clearly labeled observed-not-forecast.
- **Data:** Open-Meteo — verified: API output **CC-BY 4.0**; free tier explicitly
  covers "private or non-profit websites or apps that do not have subscriptions or
  advertising"; keyless per-user calls; required visible "Weather data by
  Open-Meteo.com" link. (Meteostat CC-BY is a clean historical backstop; its
  /license vs /faq contradiction from the old sweep is resolved at
  dev.meteostat.net/license.html.)
- **Real work found by loop 2:** the current weather block is a **const-locked
  abstention placeholder** (`conditions_snapshot.schema.json` weather def:
  every field const, `additionalProperties:false`) — filling it means new schema
  fields (provider, issued_at, values) + a new consent-gated provider lane, not
  populating an existing shape.
- **Why not high:** upstream reserves the right to block applications wholesale;
  the non-commercial free tier needs an owner decision to accept.

### 8. StatsBomb opt-in event lab (Tier B: user fetches, app never redistributes)

- **Feature:** real event-level depth for marquee tournaments — shot maps, pass
  networks, actual StatsBomb xG (labeled as theirs) — for Euro 2024, WC 2018/2022,
  Copa América 2024, **Women's Euro 2025 with 360 data**, FA WSL, Messi-era La
  Liga, and more. Isolated research pane, hard-blocked from export/training.
- **License (read in full, loop 1+2):** redistribution and commercial exploitation
  forbidden; nothing forbids a tool facilitating the user's own direct download
  from StatsBomb's GitHub (the user becomes the "User"); registration is a
  soft "ask" — surface the link; logo accreditation attaches to *publication*
  of analysis, not private local viewing.
- **What's already built:** the per-user download→verify→stage→activate→rollback
  architecture (OpenLigaDB jobs/state/policy) and isolated-pack registry; the
  StatsBomb-specific fetch/validation/store is net-new.
- **Why not high:** revocable license; owner previously excluded StatsBomb —
  this is a documented case to revisit, and it deserves its own provenance
  decision per the accepted-core rule.

### 9. Club seals — put club predictions on the record

- **Feature:** extend the seal→score loop to 2026-27 club matches so the season
  isn't just picks.
- **Real work found by loop 2:** not a flag flip — seal eligibility requires
  resolving a fixture to exactly one CC0 training pack, and openfootball club
  `source_id`s are shared across competitions (`seal.py:112-123`); needs
  per-competition pack resolution. Day-precision kickoff already yields an honest
  midnight-close window; .txt files carry kickoff times, and venue-tz→UTC
  conversion machinery exists to upgrade precision.
- **Why not high:** real design work on identity/pack resolution; depends on #1.

### 10. Wikidata reference-facts deepening

- **Feature:** managerial tenures (P286), venue history/capacity, honours and
  career facts (P54 with start/end qualifiers) as as-of-dated reference facts.
- **Data:** CC0 verified; WikiProject Association football active. Verified
  weak spots: transfer end-dates lag, fringe players patchy — so reference
  facts yes, current-squad claims no.
- **What's already built:** revision-pinned QID allowlist enrichment pack +
  Wikidata already enabled in the consent-gated research lane
  (`research/policy.py` reads the registry — adding fact types is mostly
  registry + parser work).

### 11. Deep-history club pages (footballcsv, CC0)

- **Feature:** era-badged all-time tables, promotion/relegation trajectories,
  club history research for England (multi-tier), Spain, Germany.
- **Data:** footballcsv org — CC0 dedication verified present; same
  openfootball/Gerald Bauer ecosystem; **dormant since ~2020-21** (verified) —
  fine for a deliberately historical, era-badged feature, useless for current
  seasons. Provenance rests on the same public-domain-facts theory as the
  already-accepted openfootball packs.

### 12. SkillCorner tracking showcase (MIT)

- **Feature:** the planned research pack #2 — team shape (width/depth/
  compactness), speeds, off-ball-run summaries for the 10 covered matches, loud
  era/coverage labels.
- **Data:** verified: MIT license, 10 A-League 2024/25 broadcast-tracking matches
  + season aggregates, active (pushed 2026-06-03).
- **Why not high:** feasibility is high but coverage is 10 matches — value is
  a showcase, not coverage; ~160 MB argues for opt-in download via the pack lane.

### 13. Per-match Wyscout research artifacts

- **Feature:** deepen the shipped team-level 2017/18 research summaries into
  per-match pass networks / shot maps / possession chains for the 1,941 covered
  matches (the expansion plan's original §4.5 design).
- **Data:** figshare articles re-verified CC-BY 4.0, public, no takedown. Raw
  events aren't bundled (only summaries) — a pack rebuild from figshare primary
  is needed; ~86 MB compressed argues for opt-in download.

---

## Watch list (below the confidence bar — named so they aren't re-litigated)

- **International seal lane after Jul 19:** goes dark (verified). Paths back:
  `openfootball/euro` already scopes "Euro 2028" (pushed 2026-06-26) and
  `openfootball/worldcup` covers WC qualifiers — watch for 2027 qualifier files.
  Nothing covers Sept–Nov 2026 friendlies/Nations League with an open license.
- **OpenLigaDB `ucl`/`unl` 2026-27:** shortcuts exist but are **empty shells**
  today (0 matches, verified live) — community-entered; recheck once the seasons
  start. Would remain display-only overlay regardless.
- **football-data.co.uk** (shots/corners/cards, current): stays Tier B; no
  license text at all; 2026-27 CSVs expected ~mid-August per decades-long pattern.
- **ClubElo** (no license, HTTP-only), **engsoccerdata** (non-commercial +
  provenance mix), **schochastics/football-data** (self-declared ODC-BY over
  unnamed scrape sources — laundering risk), **FiveThirtyEight SPI** (live CSVs
  dead — 302 to abcnews; archive-only), **eloratings.net** (no grant of rights),
  **FIFA ranking mirrors** (laundering): all remain excluded.
- **IDSSE** (CC-BY, DFL-authorized, 7 matches, 2.63 GB): legally clean, poor
  size/value — lab-validation only, as previously decided.

## Suggested sequencing

1. **Now → mid-August (hard-ish deadline: La Liga opens Aug 16):** #1 season
   unlock. Small parallel wins: #3 scorers, #2 women's WC history.
2. **September:** #4 Golavo Ratings, #5 Frauen-Bundesliga overlay, #6 women's
   internationals decision (Kaggle-CC0 pin or upstream LICENSE ask).
3. **October+:** #7 weather lane, #9 club seals (once #1 has soaked), #10
   Wikidata facts, #8 StatsBomb lab (needs an owner provenance decision), then
   #11–#13 research-pack depth.

Every new source still requires its own provenance review + registry entry per
the accepted-core rule; this document records the evidence for those reviews,
not a substitute for them.
