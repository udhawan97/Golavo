---
title: Games & the Match Cockpit
description: The screens you'll use — Matchday, the Match Cockpit, your score call, My Season, Leagues, Match Notes, and Model Lab.
---

Golavo opens on **games**, not on an audit form. The workbench is organized around four
surfaces: a Matchday home, the **Match Cockpit** for any indexed match, **My Season** for your
score-picking race, the **Leagues** browse hub, and **Model Lab** for expert audit machinery.
Every match also carries source-backed **Match Notes**. Below is what each does today.

## Games (the home)

The landing page is football, offline, from the first launch. It shows:

- a **recent results** rail and an **upcoming fixtures** rail drawn from the local index;
- **search over every match** in the bundled index (~100,000 games — internationals, the
  five top European leagues, and UEFA club competitions), by team or competition;
- **league shortcuts** into the Leagues hub.

A fresh install with an empty record is still a full, useful page — the app opens on the
games, not on an empty ledger. The header carries Search, an **Aa** reading-comfort control,
and a Settings gear.

## Match Cockpit

Open **any** indexed match — past or upcoming, club or international — and Golavo computes a
leak-safe multi-model read **on demand**, at the seal's own `kickoff − 1s` cutoff. A validated,
content-addressed local cache makes repeat exploration immediate; it is still a live read,
never a sealed artifact. It is presented as a six-chapter matchday programme: **form**,
**fitted style**, **history**, **model deliberation**, **verdict and your pick**, then the
optional **analyst's column**.

![Match Cockpit in Casual mode, opening with the form chapter](/Golavo/screenshots/match-cockpit.jpg)

- **Replay** — a played match, reconstructed using only data available before kickoff. It is
  **not** a forecast that existed at the time and never enters the track record; it just shows
  what the models would have said with the pre-kickoff picture.
- **Preview** — a scheduled match, with no later data to exclude.

Either way you get:

- a **Conditions Snapshot** before the programme chapters: city coordinates and elevation,
  venue-local kickoff only when the source has an exact instant, pre-match rest days, and
  great-circle travel from each side's previous indexed match. Routes use a bundled Natural
  Earth map; GeoNames and map credits stay visible. It is labeled **Context, not a model
  input**, every missing stadium/place remains **Unknown**, and weather stays an
  explicit blocked row until a lawful issued-before-kickoff history exists;
- a gold **Your call** ticket on upcoming matches. Save a score, reveal the five deterministic
  rivals, change it until kickoff, then let the final result decide the points;
- venue-aware last-five form, opponents on focus or hover, deterministic streaks, and a compact
  goal-difference trend for each side;
- a result-fitted attack and defence profile, plus guarded goal-timing and penalty-share facts
  only when the engine's notebook contains them;
- **Two voices** — Elo (ratings) and Dixon–Coles (goals) — shown side by side, with whether
  they **agree or disagree**. The Poisson variants are disclosed but never counted as extra
  opinions, and a **climatology baseline** is shown for reference. Nothing is averaged into a
  fake consensus — honest disagreement is the point.
- an **Analysis explainer** that names history support, the exact percentage-point gap between
  the two voices, known capability coverage, missing evidence, and hypothetical changes worth
  exploring. History support is not confidence, capability coverage is not accuracy, and the
  hypothetical list never changes a seal or quantifies missing lineups/injuries;
- A glanceable **Score Outlook** with the balanced over/under line, clean-sheet edge,
  and goal peak. Expert adds double chance, every total-goal threshold, clean-sheet
  comparisons, the total-goal distribution, the coherent **exact-score grid**, and the exact
  home/draw/away split in the probability mass beyond that grid.
- An honest **abstain** state when either side has too little history to model.

### Casual and Expert

Both modes keep the same chapter order and forecast values. **Casual** is a concise editorial
read: essential charts and one-line takeaways, with technical machinery kept out of the way.
**Expert** visibly adds fitted parameters, precise style values, model-range bands, baseline and
variant detail, all market rows, the exact-score matrix, source proof, and the full sealing audit.
The mode summary beneath the match header states which depth is active.

![Expert mode showing the fitted model values behind the council](/Golavo/screenshots/match-cockpit-expert.png)

The cockpit is machine-checked leak-safe: the cutoff proof rejects any training row dated at or
after `kickoff − 1s`.

## My Season

My Season is your private points race against five model rivals, scored only on matches you call.
It keeps the pick history, standings, cumulative points, exact scores, correct outcomes, bonuses,
and streaks together. See [Picks, points & My Season](/Golavo/picks-and-points/) for locking,
fingerprints, and the 3 / 1 / +1 scoring rules.

## Seal before kickoff

The cockpit is the live read; **sealing** is how you put a genuine pre-kickoff prediction on the
record — from inside the app, no CLI required. For an **eligible** fixture (men's senior full
internationals, still scheduled, inside the seal window) the cockpit shows a **Seal before
kickoff** action; it runs the same deterministic engine as the CLI (byte-identical), freezes the
model version, seed, parameters, cutoff, and inputs, and writes an immutable `ForecastArtifact`.

The action is honest about scope. A fixture that can't be sealed shows a reason-specific message
— already played, seal window closed, internationals-only, or pack unavailable — rather than a
dead button. After full time, the seal is **scored** against the actual result as a separate
successor; the original seal's bytes never change. Golavo **never** shows a retro-forecast for a
match that already kicked off — a forecast is only honest if it was sealed *before* kickoff.

> Upcoming rails and seal windows depend on what approved sources genuinely publish. Settings
> exposes each source's freshness and a manual refresh. With consent, Golavo can check on launch
> and periodically while it is open. It does not monitor after the app closes. The five bundled
> leagues carry their full 2026–27 schedules, so club fixtures appear from the first matchday;
> their results arrive when the packs are rebuilt, not from a live feed.

## Follow this match

Use **Follow** on Games or Match Cockpit to keep a fixture in a local watchlist. Golavo targets
approved-source checks at followed matches and records deduplicated kickoff, venue, score and
settlement-availability changes without changing the match identity. Conflicting or unverified
results cannot settle a forecast. Optional local notifications require explicit OS permission.

The exact product promise is: **“Golavo checks followed matches on launch and periodically only
while the app is open.”** Closing Golavo stops checks. No daemon, Login Item or LaunchAgent is
silently installed. Offline mode keeps the watchlist and event history available and shows the
last verified source freshness.

## Corrections and selected-source research

From a match, you can propose a fixture, kickoff, alias, venue or final-score correction. A source
URL and captured evidence are required before validation. Proposals are append-only untrusted
candidates; conflicts fail closed, and local acceptance is display context only. An explicit
export action is required before anything leaves the Mac.

Optional research can discover a Wikimedia page or entity for you to select. Exact source
text, retrieval time and hash are retained, deterministic parsers run before optional local AI, and
candidate facts route into the same correction queue. Search never makes a fact authoritative.

## Leagues

A browse hub with mutually exclusive **International tournaments**, **Domestic leagues**,
and **UEFA club competitions** sections.
The domestic leagues are a **historical backtesting** surface; the Champions League, Europa
League, and Conference League are historical browsing and competition-local analytics surfaces.
Their pages do not imply a complete future schedule or live club forecast. Forward sealing covers
internationals only.

Domestic league pages add competition-local strength trends and workload context,
plus a season-outlook gate that refuses to simulate an incomplete schedule. Covered
pages also carry a collapsed historical research disclosure. It names the competition
and era before showing team-only Pappalardo/Wyscout aggregates; those numbers are never
mixed with current players, current matches, forecasts, or simulations.

## Model Lab

The sealing, provenance, calibration, and evaluation machinery moved here, behind the product:

- **Track record** — the real forward calibration record, recomputed over genuine
  sealed → scored chains. It starts small because history is not available on back-order.
- **Backtests** — held-out chronological fold metrics (log loss, Brier, ECE, RPS) and reliability
  diagrams, kept strictly separate from the forward record.
- **Methodologies** — why three of the five model families are really one voice, and how
  abstention works.
- **Sealed forecasts** — the immutable forecast list.

Old `#/ledger` and `#/eval` links redirect into the Lab, so existing bookmarks keep working.

## Match Notes

Every match page carries Match Notes: deterministic, source-backed facts computed at the same
`kickoff − 1s` horizon, so it can never read the match's own result or anything later. Facts are
labelled **predictive / context / coincidence**, each with its sample, base rate, source, and
freshness. Coincidences are capped and quarantined ("for the pub, not the forecast") and are
never shown to the AI. Nothing here changes a forecast — the fact package has a machine-checked
rule that forbids it from importing any forecast, model, or calibration writer.

The magazine-style read also surfaces **signature form stats** most scoreboards never show —
both-teams-scored rate, scoring momentum, clean-sheet rate, and the goal character of the
head-to-head — and it is **de-duplicated** from the "three things to know" insight cards, so the
Notebook is the deeper cut rather than a repeat. See the
[Fact & Coincidence engine](/Golavo/methodology/facts/) and
[Match Notes & optional enrichment](/Golavo/match-enrichment/) pages.

## AI Analyst Read *(optional, off by default)*

An optional narrative and scenario synthesis, always subordinate to the deterministic numbers.
It reads and connects the match's notes and model council (and sealed forecasts), cites only the
engine's numbers, and can never change one. The result opens with a verdict, groups the strongest
findings and scenarios for a quick read, keeps exact evidence behind disclosure, and separates
opt-in web findings under a not-engine-verified badge.

Choose **Fast** for a short read from the smaller assigned model, or **Deep analysis** for more
evidence and connected scenarios from the larger model (usually 5–8 minutes). The panel reports
whether local AI is ready and includes a compact **Get or manage local models** guide. The web
research checkbox lives beside the read so network use is visible when you request it. It runs
locally (Ollama / llama.cpp) or via BYOK cloud. See [AI providers](/Golavo/ai/providers/).
