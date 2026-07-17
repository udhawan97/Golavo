---
title: Competition analytics
description: Strength trends, report cards, season and tournament outlooks, historical team research, and the boundaries between them.
---

Golavo keeps four kinds of competition analysis separate because they answer
different questions and carry different time guarantees.

## Existing-data analytics

Domestic leagues and UEFA club competitions can show **competition-local strength
trends** and **rest/congestion** derived from the indexed matches. A value of 100 is
that competition's own baseline; it is not a cross-league power ranking. Report cards
use chronological held-out seasons and seeded match-bootstrap intervals.

Schedule difficulty is not calculated until the remaining fixture list is complete.
An absent schedule is a blocked capability, never a set of zeroes.

## Tournament and season outlooks

The World Cup 2026 outlook exactly enumerates the resolved four-team bracket for the
Ratings voice, Goals voice, and equal-chance baseline. The voices stay separate and
the disclosed knockout rule resolves regulation draws. This is a current simulation,
not a sealed prediction and not part of the forecast ledger.

Domestic standings use verified competition-specific rules, including known points
adjustments in the validation season. The seeded 10,000-run outlook can start only
after Golavo certifies every team, ordered home/away pair, past result, and remaining
fixture. All five bundled leagues now pass that certificate for 2026/27 — their full
published schedules are pinned from the OpenFootball Football.TXT country repos — so
the outlook runs. The certificate is still checked on every request, and a league that
ever fails it produces the blocked state and no probabilities rather than a guess.

## Golden Boot and shootouts

An international competition shows a leading-scorers table and a penalty-shootout
ledger, built from the bundled martj42 goalscorers and shootouts records. Both are
leak-safe: they count only matches played by the requested cutoff, so a completed
player's tally is fixed and rewinding the clock removes later goals. Own goals are
never credited to a scorer. Neither table carries a competition column upstream, so
each is joined to the match index by date and teams to attach the competition.

This data ships only for men's internationals, so a club competition reports a typed
"no scorer data" state rather than an empty table — the same first-class unknown the
rest of the app uses.

## Historical team research

The isolated Pappalardo/Wyscout CC-BY-4.0 pack contains seven team-only summaries:
the 2017/18 Premier League, La Liga, Bundesliga, Serie A, and Ligue 1; Euro 2016;
and World Cup 2018. Together they cover **1,941 matches and 3,251,294 events**.

Each collapsed panel names its competition and era before exposing pass completion,
progressive passes, shots, goals, a disclosed same-team event-run proxy, and Golavo's
own 12×8 research-xT calculation. It does not ship raw events or player identities,
does not claim observed xG, and never enters a current forecast or simulation.

## Conditions and weather

Conditions Snapshot is display-only. Pinned GeoNames and Natural Earth resources can
provide exact city context, local kickoff, elevation, rest, travel distance, and an
offline route map. Stadium remains unknown without stadium-level evidence.

Weather is explicitly **blocked**. Golavo will not replace the forecast that was
available before kickoff with observed weather gathered afterwards. Until a licensed
source preserves issued-at history, the contract has no weather source id or value and
states `model_input: false`.

See [Coverage](/Golavo/data/coverage/) and [Sources & licenses](/Golavo/data/sources/)
for exact eras, licenses, and exclusions.
