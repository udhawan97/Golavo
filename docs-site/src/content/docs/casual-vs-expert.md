---
title: Casual vs Expert
description: Two presentation depths over the same sealed numbers. Different depth never means different certainty.
---

Every forecast detail page has a **Casual ⇄ Expert** toggle (top-right, persisted like the theme). It changes how much is shown — never the probabilities. The 1X2 verdict bar and its plain-language headline are byte-for-byte identical in both modes.

| | Casual | Expert |
|---|---|---|
| Verdict | verdict bar + plain-language headline | verdict bar + plain-language headline |
| Reading | one-sentence summary + a few cited, sealed-number facts | — |
| Score matrix | hidden | full exact-score **heatmap** with the `N+` tail bucket |
| Spread | most-likely score + expected goals (as facts) | most-likely score, expected goals, tail probability |
| Versions | hidden | model id, engine version, seed, params hash, code sha, training cutoff |
| Calibration | hidden | uncertainty flag + link to the prediction ledger |

The Commentator's Notebook and the optional AI Deep Read sit below the fold in **both** modes, always subordinate to the sealed numbers.

## Two rules that hold in both modes

1. **Depth never changes displayed certainty.** The same probability bar, the same numbers. A fuller layout is not a more confident forecast.
2. **AI text is always visually subordinate to the sealed numbers.** The engine speaks first; the AI panel is recessed, off by default, and can never change a number.

## Casual phrasing is band-generated, not AI

The one-line verdict comes from `ui/src/lib/summary.ts` — a pure function of the sealed probabilities and the score matrix, mapping them through **fixed phrase bands**. The same artifact always yields the same words, and the words never claim more certainty than the numbers do:

| Leading probability | Team phrasing |
|---|---|
| ≥ 65% | "strong favourites" |
| ≥ 50% | "favoured" |
| ≥ 42% | "narrow favourites" |
| below, and within 6 pts of #2 | "too close to call" |

A leading **draw** reads "favoured / narrowly favoured / the marginal pick" on the same thresholds. No AI is involved; the cited facts beneath are labelled *"straight from the sealed model — no AI wrote these."*

## The heatmap (Expert)

The Expert view renders the sealed `score_matrix` as an accessible table: real row/column headers, tabular numerals, a per-cell screen-reader label, and the most-likely scoreline outlined and starred. The heat tint is mixed over the surface so cell text stays legible in light and dark themes, and all motion is CSS-only (so the global reduced-motion rule covers it). Its win/draw/loss totals reproduce the verdict bar exactly — that is [enforced on load](/Golavo/methodology/prediction/#exact-score-distribution--coherence-phase-8). When the model family forecasts outcomes rather than goals, or the seal abstained, the heatmap is replaced by an honest "no exact-score distribution" note — never a fabricated grid.
