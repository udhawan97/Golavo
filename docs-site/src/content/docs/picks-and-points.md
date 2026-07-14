---
title: Picks, points & My Season
description: Call a score before kickoff, prove it stayed locked, and race five transparent model rivals across your season.
---

Picks are Golavo's private score-calling game. They are separate from **sealing**: a pick is
*your* call and scores simple game points; a seal is the expert trust record for a model forecast.
Neither involves money, odds, an account, or a hosted leaderboard.

## Make a call

Open any upcoming match and use the gold **Your call** ticket. Choose the home and away score,
save it, and edit or remove it freely before kickoff. Golavo hides the five model calls until
you save yours, so they cannot anchor the score you choose.

At kickoff the record becomes immutable. Its canonical JSON receives a SHA-256 fingerprint;
if the locked bytes changed later, verification would fail. When only a match date is known,
the call locks conservatively at 00:00 UTC as that match day begins.

## Points

| Call | Points |
| --- | ---: |
| Exact final score | **3** |
| Right outcome — home win, draw, or away win | **1** |
| Strictly beat every available model rival | **+1** |

Exact-score and outcome points stack. The bonus requires a strict win; a tie with the best rival
does not earn it. A rival that abstains is ignored, and if all five abstain no bonus is available.
Skipping a match costs nothing: you and the rivals are compared only on matches you play.

## The five rivals

- **Goal Machine**, **Plain Goals**, and **Twin Goals** call an exact score from their stored
  score matrices.
- **Form Ranker** and **History Buff** call only the outcome, so each tops out at one point.
- An abstaining model makes no call. Golavo never manufactures an exact score from 1X2
  probabilities.

The rivals are deterministic projections of the same pre-kickoff analysis shown in the cockpit.
Their snapshot is pinned into your locked record, so the comparison cannot drift after kickoff.

## My Season

**My Season** totals your points, exact scores, outcomes, bonuses, current streak, and best streak.
The standings and points race include the same five rivals, filtered to the matches you called.
Draft, locked, scored, and voided records remain distinct; voided matches do not break a streak.

In the web preview, picks live only in that browser's local storage and are prominently labelled
**Practice mode — never counted**. In the desktop app they live under the local ledger directory
and survive restarts. No pick is uploaded.

:::note[No gambling mechanics]
There is no money, wagering, odds feed, public account, or prize. Picks are a local comparison
between your football judgment and five disclosed deterministic methods.
:::

For the model-trust workflow, see [Model Lab & the track record](/Golavo/prediction-ledger/).
