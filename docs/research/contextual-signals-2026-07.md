# Per-club home advantage and rest days: a measured negative result

**Date:** 2026-07-18
**Status:** candidate registered and published; **not** seated on any council
**Code:** `ContextualDixonColesModel` in `core/golavo_core/models/candidates.py`

## What was tried

A sixth candidate family, `contextual_dixon_coles`, extending Dixon-Coles with the
two signals most often named as cheap wins for a club model — both derivable from
data already on disk, neither needing a new source:

1. **Per-club home advantage.** The frozen five apply one league-wide home boost
   to every club, so a fortress (strong at home, ordinary away) has its two forms
   averaged into a single strength. The candidate estimates each club's home
   split against the base fit's own expectation and shrinks it toward 1.0.
2. **Rest days.** Days since each side last played, read from the fixture list by
   `schedule_rest_days`, bucketed into short (≤3 days), normal (4–9) and long
   (≥10), with a multiplier per band estimated against base expectation.

The candidate shares Dixon-Coles' tuned decay (`xi`) deliberately, so the pair
differs by these two signals and nothing else and any gap is attributable.

## The gate

Ship as a council voice if it beats **at least the median incumbent** on log loss
and RPS across the five bundled leagues; publish the full evaluation either way.

| League | Log loss vs median | RPS vs median | Rank (of 6) |
|---|---|---|---|
| Premier League | 1.00972 vs 1.00650 — fail | 0.21357 vs 0.21303 — fail | 4th |
| La Liga | 0.99172 vs 0.98983 — fail | 0.19858 vs 0.19761 — fail | 4th |
| Bundesliga | 1.01990 vs 1.01603 — fail | 0.21147 vs 0.20960 — fail | 5th |
| Serie A | 1.00563 vs 1.00715 — **pass** | 0.20262 vs 0.20209 — fail | 2nd |
| Ligue 1 | 1.01744 vs 1.01476 — fail | 0.21370 vs 0.21299 — fail | 4th |

**Beat the median incumbent on log loss in 1 of 5 leagues, on RPS in 0 of 5.**
The gate fails, so the family is registered and evaluated but seats no council.

## Why it fails — the part worth keeping

The backtest says the candidate is not competitive. Two diagnostics say *why*,
and they are the reusable finding: **neither signal exists in this data.**

### Per-club home advantage does not persist

Across 24 Premier League clubs with 76+ home matches in the training era, the
ratio of home to away goals per match has mean 1.281 and standard deviation
0.140 — a spread that looks like real per-club variation.

It is not. Splitting the training era in half and correlating each club's home
edge in the first half against its own edge in the second gives:

```
split-half correlation r = -0.007   (20 clubs in both halves)
```

Zero. A club's home edge in one era carries no information about its home edge in
the next, which means the observed spread is sampling noise around the
league-wide home advantage the frozen five already model. There is nothing stable
to estimate, so no amount of shrinkage tuning recovers a signal — harder
shrinkage simply converges the candidate onto plain Dixon-Coles.

### The rest effect has no consistent sign

Across all 15 fitted league-seasons (5 leagues × 3 folds), the short-rest band
minus the normal-rest band comes out:

```
mean   +0.0010   (a tenth of one percent)
sd      0.0350   (three and a half percent)
sign   above normal in 8 of 15 folds, below in 7
```

The scatter between folds is **thirty-five times larger than the average effect**,
and the sign is a coin flip. Individual folds look like signal in both directions
— Bundesliga 2022-23 puts short rest at 0.934, Serie A 2022-23 at 1.041 — but
they do not agree with each other, which is what a measurement of nothing looks
like when it is resampled fifteen times.

> An earlier draft of this note reported "short rest scores marginally *more*"
> from a single Premier League fit. That was one fold's noise read as a trend;
> the fifteen-fold table above is the honest version. The correction is recorded
> rather than quietly replaced, because the mistake — generalising a direction
> from one fit — is the same mistake this whole document is about.

A real fatigue effect may still exist and be masked by confounding: the clubs
playing midweek are the ones in European and cup competition, and the base model
already prices their strength through attack and defence. Isolating it would need
a control for opponent strength and competition that a league-wide band cannot
express — which makes it a different, larger piece of work, not a tuning pass.

## The tuned-decay fallback: what was and was not run

The agreed fallback if the gate failed was "iterate signals — tuned decay is next
in line". Two things are true and neither is quite "it was tried":

1. **Per-fold decay tuning already applies to this candidate.**
   `_tune_dixon_coles_xi` selects `xi` on a pre-cutoff validation year, and
   `_evaluate_folds` hands the winner to `dixon_coles` *and*
   `contextual_dixon_coles` alike. So the candidate is not running on a
   hardcoded decay; it is running on a tuned one.
2. **Widening the search was deliberately not done unilaterally.** The grid is
   `(0.0005, 0.001, 0.002)` — half-lives of roughly four, two and one years. If
   club form really decays faster than that, the grid is the binding constraint,
   and widening it is the obvious next experiment. But the same tuner feeds
   `dixon_coles`, so widening it **moves a frozen model's published numbers**.
   That is a decision about what "frozen" means, not a tuning detail, and it
   belongs to whoever owns the project rather than to this pass.

The honest summary is therefore: decay tuning is in effect, a wider decay search
is untested, and it is the one lever here that could still move a number — though
it would lift Dixon-Coles alongside the candidate rather than close the gap
between them, since the two share the value.

## Known limitation of this implementation

The home edge is estimated as a *post-hoc residual* against a base model fitted on
the same rows, so the base fit has already absorbed part of any home split into
the pooled attack/defence strengths. A stronger formulation would estimate a
per-club home parameter jointly in the likelihood, or fit attack/defence from away
matches only and treat home matches as the residual.

Given the split-half correlation of −0.007, a better estimator is expected to
estimate the same noise more precisely, so this was not pursued. Anyone revisiting
it should re-run the persistence test first: **if `r` is still near zero, the
signal is not there and the estimator is not the problem.**

## What shipped anyway

- `schedule_rest_days` — a score-blind rest-days helper, reusable by any future
  candidate and proven not to read a result.
- The `_prediction` extraction on `PoissonModel`, so every goal-modelling family
  assembles its probabilities and score matrix through one coherent path.
- An explicit `SCORED_RIVAL_FAMILIES` roster, separating "families that exist"
  from "rivals the season game scores you against" — the season race stays five
  rivals however many candidates the registry grows, so a new voice can never
  silently restate "beat all five models" as a different bet. Mirrored in the UI
  as `ScoredRivalFamily`, from which `ModelFamily` is now derived.
- `FROZEN_FAMILIES` beside `FAMILIES`, which is what makes "a candidate on trial"
  expressible at all. A candidate is fitted and reported; only a frozen family
  may be seated on a council, sealed into an artifact, or scored as a rival. That
  boundary is enforced in four places rather than assumed: `evaluate` (no
  candidate touches an international fold), `artifacts.py` and the CLI (a seal is
  permanent, so a revisable candidate may not make one), and `derive_rival_picks`.

## What this cost, honestly

Three things this pass got wrong and then corrected, recorded because the
corrections are the useful part:

1. The first draft **seated the family on club councils** before the backtest had
   run. Doing so would also have silently added a sixth rival to the season game,
   because `derive_rival_picks` reads whatever the council contains — quietly
   rewriting the rule every existing season was played under.
2. The first evaluation run **let the candidate into the internationals folds**,
   which moved every incumbent's published rank in a report that was supposed to
   stay untouched. Fixed by giving `evaluate` an explicit family list.
3. The first version of this document **generalised the rest direction from a
   single fold** — the mistake it exists to warn about. See the note above.

## Re-running the evidence

```bash
cd core
python -m golavo_core evaluate-club --pack ../packs/openfootball-eng-pl \
  --summary ../docs/handoff/eval_summary_epl.json \
  --report  ../docs/handoff/eval_report_epl.md
```

Swap the pack for `openfootball-esp-ll`, `-deu-bl`, `-ita-sa`, `-fra-l1`.
