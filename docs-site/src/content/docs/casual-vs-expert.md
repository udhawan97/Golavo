---
title: Casual vs Expert
description: Two presentation depths over the same sealed numbers. Different depth never means different certainty.
---

Every forecast detail page has a **Casual ⇄ Expert** toggle (top-right, persisted like the theme). It changes how much is shown — never the probabilities. The 1X2 verdict bar and its plain-language headline are byte-for-byte identical in both modes.

The page reads top-to-bottom as: a calm **match header** (teams, competition, date, venue — the raw ids are demoted to the provenance drawer), the one-line **trust strip** ("Sealed before kickoff · Deterministic · AI never changes the numbers", each with an ⓘ for the detail), the verdict bar, a short **In plain terms** reading, **Three things to know**, the Commentator's Notebook, and the expert drawers.

| | Casual | Expert |
|---|---|---|
| Verdict | verdict bar + plain-language headline | verdict bar + plain-language headline |
| Reading | *In plain terms* — most-likely outcome/score with a natural-frequency gloss ("about 3 in 5"), expected goals, uncertainty | same |
| Three things to know | 3 fixed-rule picks from the notebook | same |
| Score matrix | in a **collapsed** drawer | drawer **opened** — full exact-score **heatmap** with the `N+` tail bucket |
| Goal/outcome summaries | collapsed drawer | opened drawer |
| Model & versions | collapsed drawer | opened — model id, engine version, seed, params hash, code sha, training cutoff |
| Provenance & inputs | collapsed drawer | opened — per-snapshot source, sha256, retrieved-at, plus the demoted match/artifact ids |
| Calibration | collapsed drawer | opened — uncertainty flag + link to the prediction ledger |

The expert drawers are native `<details>` accordions: **collapsed** in Casual and **opened** in Expert, but a Casual reader can still expand any one — depth is progressive disclosure, not a hard wall. The Commentator's Notebook and the optional AI Deep Read sit below in **both** modes, always subordinate to the sealed numbers.

**Percentages are whole numbers** in the verdict bar and readings (both modes), so the UI never implies precision the model doesn't have; the three 1X2 figures are rounded by largest-remainder so they still sum to 100. One decimal survives only in the expert heatmap, ledger, and evaluation tables.

## Three things to know

A small, scannable summary above the notebook, built **only** from facts the engine already computed and picked by a pure, documented rule in `ui/src/lib/insights.ts`: predictive (labelled base rate) facts before context, then by specificity, then sample size, then a stable id tie-break; coincidences are never eligible and stale facts are dropped. The same notebook always yields the same three facts — which is why the panel is labelled *"chosen by fixed rules · not AI."* Nothing is written or re-weighted by AI.

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
