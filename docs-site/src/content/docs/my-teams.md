---
title: My Teams
description: Keep exact club favorites locally and bring their table, one season-outlook voice, run-in, stakes, follows, and picks into one room.
---

:::note[Availability]
My Teams is verified on repository `main` after v0.18.0. It is not in the v0.18.0
desktop installers. Run or build the current source to use it before the next release.
:::

My Teams is a local club room, not an account or a new forecast. It reuses the season
outlook that Golavo already certifies for the five bundled domestic leagues and stores
only the exact competition/team favorites you choose in the browser preference store.

![My Teams on source main showing a local Augsburg favorite, projected points, five run-in fixtures, and guarded season-stake swings](/Golavo/screenshots/my-teams-source-main.png)

*Source-main evidence after v0.18.0, captured against the local engine; this screen is not
in the current installers.*

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
