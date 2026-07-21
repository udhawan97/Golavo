---
title: Fact & Coincidence engine
description: The Commentator's Notebook — deterministic, source-backed match facts, labelled predictive / context / coincidence, sample-guarded, and unable to change a forecast.
---

The **Commentator's Notebook** is Golavo's honest answer to "tell me something about this
match." It computes deterministic, source-backed facts over the vendored CC0 packs. Its whole
design goal is that **a coincidence never masquerades as evidence, and a fact never changes a
number**.

Every fact is labelled, carries its sample and source, and is sample-guarded. A fact can inform
how you *read* a match; it can never move a probability. That last property is not a promise — it
is [machine-checked](#the-no-write-invariant).

## Three labels, and why the distinction matters

Every fact wears exactly one label, and the UI groups them by it:

- **Context** — background the fixture sits in: form streaks, head-to-head records, biggest wins,
  home/away form, clean-sheet runs, neutral-venue records. It describes the past; it makes no
  claim about the future.
- **Predictive** — a base rate with genuine forward signal, reported *as a base rate* and clearly
  labelled: e.g. the home-win rate in this competition, or the first-year win rate of teams newly
  arrived in it. **A predictive fact here is never fed to the forecast model.** The engine consumes
  signal only through its own typed-feature gate; the Notebook only reports the number so you can
  see it.
- **Coincidence** — calendar and pattern quirks with no forward signal (a repeated scoreline, a
  day-of-week run). These are **quarantined**: capped, walled off in the UI as "for the pub, not
  the forecast," and never shown to the AI layer.

Keeping these three apart is the point. A base rate and a coincidence can look identical — both are
"X happened in Y of Z matches." The difference is whether the pattern carries signal, and Golavo
commits to that judgement *before* seeing the data, in the template's registered label.

## Signature form stats

Alongside the streaks and records, the Notebook computes the unusual form insights a commentator
knows but most scoreboards never show — all `context`, all deterministic and number-disciplined,
all running under the same sample and freshness guards:

- **both-teams-scored rate** — how often a side's recent matches see both teams find the net;
- **scoring momentum** (`scoring_trend`) — goals a game over the last six versus the stretch
  before, surfaced only when the shift is real;
- **clean-sheet rate** — how reliably a defence shuts the door (distinct from the current
  clean-sheet *streak*);
- **head-to-head goal character** (`head_to_head_goals`) — the average goals and both-scored
  count in the meetings, the dimension the win/draw/loss record leaves out.

**No overlap with the headline picks.** The home page's "three things to know" insight cards are a
pure, documented pick from this same notebook; the full Notebook below **removes** those picks, so
the two panels partition the facts rather than repeat them — the Notebook is the deeper cut.

Inside that deeper cut, scope stays visible: competition-wide base rates have their own context
band, the same team template appears as one direct-comparison row, and facts held by only one side
stay in that team's lane. The layout never invents a missing value to make a pair look complete.

## Base rates and samples

Every fact carries `sample_n` (the observations it is built on), `denominator` (the base-rate
denominator, equal to `sample_n` for non-rate facts), and, for a rate, `base_rate` in `[0, 1]`.
The base rate is stated in plain language *in the fact text itself* — "the home side has won 45.7%
of 3685 non-neutral matches" — not buried in a tooltip.

**Minimum-sample suppression.** Each template declares a floor. A rate claim whose denominator is
below the floor, or a "streak" shorter than its floor, is **suppressed** — dropped, not shown with
a caveat. Suppressed candidates are recorded in the notebook's `suppressed` audit list with the
reason, so the guard is visible rather than silent.

**Staleness auto-hide.** Form facts carry a freshness window. If the most recent match behind a
fact is older than that window (measured against the seal's information horizon, not a wall clock —
so the result stays deterministic), the fact is auto-hidden. Structural, all-time facts ("biggest
win in this data") never go stale.

## The multiple-comparison bound

Search a big enough pile of data for *any* striking pattern and you will always find one. Golavo
refuses that game structurally:

- The template family is **fixed and pre-registered per release.** The notebook reports its
  `family_size` — the number of hypotheses the family evaluates for one match (currently **52**).
  This number is a constant of the code, **not a function of the data**: the engine cannot widen
  its search until something looks significant.
- Coincidences are **ranked by specificity, never by a significance test.** There is no p-value to
  hunt, and no reward for a surprising-looking pattern.
- Adding, removing, or re-labelling a template bumps the registry version and is a reviewed, logged
  change. The bound only moves in the open.

## Coincidence quarantine

Coincidence-labelled facts are capped at **three** per match, ranked by a deterministic specificity
score (longer runs and rarer patterns rank higher). Anything past the cap is suppressed and logged.
In the UI they sit in a visibly separate, dashed "for the pub, not the forecast" block; in the data
pipeline they are **never folded into the AI evidence bundle.** The model cannot cite a coincidence
because it never sees one.

## Facts and the AI layer

Golavo's optional [AI narration](/Golavo/ai/providers/) is governed by a numeric whitelist: the
model may only state numbers the deterministic engine already produced. Notebook facts extend that
whitelist honestly. Every fact's text is **number-disciplined** — every digit in it is one of the
fact's declared numbers — so a context or predictive fact folds verbatim into the bundle's
`allowed_numbers`. The model may then cite the fact, but it can no more invent a notebook number
than an engine one. Coincidences are excluded from the fold entirely.

## Internationals-only scorers and shootouts

The martj42 internationals pack ships goalscorers and penalty-shootout records; the openfootball
league packs ship results only. So scorer and shootout facts are computed **for internationals
only**. There is no accepted open-source club scorer or lineup dataset, and Golavo does not invent
one — those templates simply do not run for a club fixture. No club scorer, assist, or lineup fact
is ever fabricated.

The promoted-team base rate is a related honesty case. The CC0 single-league packs carry no
division tier, so a genuine promotion cannot be detected. Golavo reports instead a **debut-window**
proxy — the first-year win rate of teams that first appear mid-dataset (teams present from the first
season are excluded as left-censored) — and labels it as exactly that, never as "promoted."

## Club-only half-time facts

The openfootball club packs include a recorded half-time score for many, but not all, matches.
Golavo uses those rows for two `context` templates: recovery after trailing at half-time, and
conversion after leading at half-time. Both run once per team, have fixed sample floors, and become
stale after 400 days at the fixture's information horizon.

Rows without a well-formed two-integer `score.ht` are ignored. If a recorded half-time score
exceeds the corresponding final score, ingest fails as corrupt instead of silently accepting it.
The UI says plainly that older seasons contain gaps; no missing half-time result is inferred.

## World Cup pedigree (isolated CC-BY-SA pack)

For an exact `FIFA World Cup` fixture, two additional `context` templates read the isolated
Fjelstul pack: `wc_pedigree` counts men's tournament appearances, titles, finals and the best
finish among the team's five most recent appearances; `wc_awards` lists the recorded individual
awards won by that team's players. The pack is CC-BY-SA-4.0 and credited in the source docs and
third-party notices.

Every tournament is filtered by its **end date** against the fixture's information horizon. A
replay during the 2014 tournament can see history only through 2010 — not the unfinished 2014
edition, and never 2018 or 2022. The pack remains outside `golavo_core.ingest`, the joined match
index, model fitting, and forecast features; it supplies descriptive facts only.

## The no-write invariant

The honesty guarantee is enforced two ways, both checked by tests rather than by discipline:

1. **Isolation (static).** Every module in the facts package is parsed and asserted to import none
   of the forecast, model, calibration, or artifact-writer code. No facts code path *can* reach a
   writer.
2. **Immutability (runtime).** The full notebook + AI-fold pipeline is run over a real sealed
   artifact and the artifact's forecast/evaluation bytes are asserted unchanged; folding notebook
   facts into an evidence bundle is asserted to only *append* — every engine number keeps its exact
   id, value, and display.

Together these are the machine-checked statement that a fact never touches a number.

## The template catalogue (v2026.07.12)

| Template | Label | Scope | Min sample | Staleness | Source |
| --- | --- | --- | --- | --- | --- |
| `unbeaten_run` | context | team | 3 | 400 d | results |
| `winless_run` | context | team | 3 | 400 d | results |
| `win_streak` | context | team | 3 | 400 d | results |
| `clean_sheet_run` | context | team | 3 | 400 d | results |
| `home_away_form` | context | team | 5 | 400 d | results |
| `biggest_win` | context | team | 10 | none | results |
| `head_to_head_record` | context | head-to-head | 3 | 12 y | results |
| `neutral_venue_record` | context | team | 5 | none | results |
| `both_teams_scored_rate` | context | team | 10 | 400 d | results |
| `clean_sheet_rate` | context | team | 10 | 400 d | results |
| `scoring_trend` | context | team | 12 | 400 d | results |
| `head_to_head_goals` | context | head-to-head | 4 | 12 y | results |
| `top_scorer` | context | team | 10 | none | goalscorers (internationals) |
| `shootout_record` | context | team | 3 | none | shootouts (internationals) |
| `home_advantage_base_rate` | predictive | competition | 100 | none | results |
| `competition_debut_base_rate` | predictive | competition | 200 | none | results |
| `day_of_week_streak` | coincidence | team | 4 | 400 d | results |
| `scoreline_repeat` | coincidence | head-to-head | 2 | none | results |
| `calendar_date_repeat` | coincidence | team | 3 | none | results |

All facts cite the vendored snapshot they were computed from (a byte-pinned pack), and are
byte-identical for the same pack — the same guarantee the forecasts carry.
