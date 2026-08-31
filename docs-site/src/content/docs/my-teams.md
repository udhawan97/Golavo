---
title: My Teams
description: Keep exact club favorites locally; source main adds an Unreleased dossier that separates observed record, model voices, and competition-scoped evidence.
---

My Teams is a local club room, not an account or a new forecast. It reuses the season
outlook that Golavo already certifies for the five bundled domestic leagues and stores
only the exact competition/team favorites you choose in the browser preference store.

![My Teams showing a local Augsburg favorite, projected points, five run-in fixtures, and guarded season-stake swings](/Golavo/screenshots/my-teams-source-main.png)

## Add a club

1. Open **My Season → My Teams**, or use the footer's **My Teams** link.
2. Choose one of the five domestic leagues with an available season outlook.
3. Choose a club from that outlook's current table.

The favorite is keyed by the exact competition id and team name. If a later season no
longer contains that identity after a rename, promotion, or relegation, Golavo preserves
the saved value and shows an unavailable state. It does not guess a replacement club.

## What a club card shows

When the local outlook is available, a card can show:

- current table points and projected final points;
- title, top-four, and relegation chances from one disclosed model voice;
- the next five remaining fixtures;
- a guarded largest season-stake swing when both conditional branches have enough runs;
- whether each fixture is followed and whether you have made a score pick;
- the live follow/unfollow control from Golavo's one complete shared follow list;
- a like-for-like local projection change after the source index changes, but only when
  competition, season, team, voice, rule, seed, and iteration count still match;
- direct links to the league and match views.

In source `main` (**Unreleased**), the club name opens a dedicated **team dossier**.
Current-season form boards on league pages use the same exact-identity route, so both entry
points resolve the same competition and club pair. The installed v0.19.0 release does not yet
include this page.

## Read the team dossier

The dossier follows one fixed evidence order:

1. **Observed record** — certified table position, points, record, goals, and exact current
   form when that competition sample contains the same team identity.
2. **Model projections** — the complete set of available model voices, each in its own card.
   If any model voice lacks the exact team identity, the whole comparison is withheld rather
   than presenting a partial or cherry-picked set. The voices are never averaged into a
   consensus and the simulation is never presented as a seal.
3. **Evidence context** — competition-scoped Golavo Ratings, strength, workload, and
   schedule difficulty. Optional context can be unavailable without hiding the observed table.

The next-five run-in keeps the match and follow action together; the match link is the explicit
route to view or make a pick. Reading the dossier does not load or settle pick records. Guarded
importance is attributed to the exact model voice that produced it.
The colophon repeats the source ids, as-of instant, and index fingerprint. If the active
table does not contain the exact team name, the entire dossier fails closed before showing
any model projection.

Thin conditional branches keep the stake held back. The room never blends model voices,
re-simulates a fixture in the UI, turns an outlook into a seal, or presents advice.

## Move the shortlist

**Export My Teams** writes a small versioned JSON file containing only exact competition
ids and team names. **Preview import** parses a bounded file and checks every identity
against the current local league catalog and certified table before enabling Apply. Imported
league labels and routes are never trusted because the file cannot contain them. The default
merges verified clubs; replacing the current shortlist requires a separate checkbox.

This transfer is for preferences only. It does not carry forecasts, source data, account
state, provider settings, or a claim that a club identity still exists.

## Local-data boundary

Team favorites live in `localStorage` under `golavo.favorite-teams.v1`. They do not create
an account, enable a network provider, change a forecast, or sync between devices. They
are intentionally excluded from the forecast-ledger archive because that archive covers
engine-owned artifacts, picks, and followed-match state—not browser preferences.

See [Competition analytics](/Golavo/competition-analytics/) for the outlook and importance
rules, and [Picks, points & My Season](/Golavo/picks-and-points/) for the separate score game.
