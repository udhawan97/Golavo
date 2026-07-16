---
title: Casual vs Expert
description: Two presentation depths over the same sealed numbers. Different depth never means different certainty.
---

The Match Cockpit and every sealed forecast detail page have a **Casual ⇄ Expert** toggle
(top-right, persisted like the theme). It changes how much is shown — never a probability.
The active depth is stated beneath the match header so the change is visible before you scroll.

On the Match Cockpit, both modes follow the same six chapters: form, fitted style, history,
model deliberation, verdict and pick, then the optional analyst column. **Casual** keeps the
essential story and compact charts. **Expert** adds full model values, market rows, sources,
and audit context in place, without rearranging the page.

The page reads top-to-bottom as: a calm **match header** (teams, competition, date, venue — the raw ids are demoted to the provenance drawer), the one-line **trust strip** ("Sealed before kickoff · Deterministic · AI never changes the numbers", each with an ⓘ for the detail), the verdict bar, a short **In plain terms** reading, **Three things to know**, the Commentator's Notebook, and the expert drawers.

| | Casual | Expert |
|---|---|---|
| Match programme | concise chapter introductions, fixed-rule pull numbers, essential charts and takeaways | same order, plus precise style values, model-range bands, fitted parameters, full markets and source proof |
| Model council | each voice and a plain-language explanation of disagreement | adds the outcome range, Elo and Dixon–Coles internals, climatology baseline, and goal-model variants |
| Score Outlook | headline score/goal tiles, key split bars, and one quick market takeaway | adds double chance, all goal thresholds, clean-sheet comparison, goal distribution, beyond-grid outcome split, and exact-score matrix |
| Match evidence | guarded facts and visual summaries | adds source/sample/freshness proof where the payload provides it |
| Verdict | verdict bar + plain-language headline | verdict bar + plain-language headline |
| Reading | *In plain terms* — most-likely outcome/score with a natural-frequency gloss ("about 3 in 5"), expected goals, and training-history support | same |
| Three things to know | 3 fixed-rule picks from the notebook | same |
| Score matrix | in a **collapsed** drawer | drawer **opened** — full exact-score **heatmap** with the `N+` tail bucket |
| Goal/outcome summaries | collapsed drawer | opened drawer |
| Model & versions | collapsed drawer | opened — model id, engine version, seed, params hash, code sha, training cutoff |
| Provenance & inputs | collapsed drawer | opened — per-snapshot source, sha256, retrieved-at, plus the demoted match/artifact ids |
| Calibration | collapsed drawer | opened — history-support coverage (not confidence) + link to the prediction ledger |

On sealed forecast pages, expert drawers remain native `<details>` accordions: **collapsed** in
Casual and **opened** in Expert. In the Match Cockpit, the deepest model and market blocks are
Expert-only so the Casual programme stays genuinely concise. The deterministic verdict and the
optional AI read remain in both modes, with AI always subordinate to the engine's numbers.

**Percentages are whole numbers** in the verdict bar and readings (both modes), so the UI never implies precision the model doesn't have; the three 1X2 figures are rounded by largest-remainder so they still sum to 100. One decimal survives only in the expert heatmap, ledger, and evaluation tables.

## Three things to know

A small, scannable summary above the notebook, built **only** from facts the engine already computed and picked by a pure, documented rule in `ui/src/lib/insights.ts`. The rule leads with the facts **closest to this fixture**: by scope (head-to-head → match → team → competition), then specificity, then predictive-before-context, then sample size, then a stable id tie-break; coincidences are never eligible and stale facts are dropped. So a head-to-head record surfaces above a competition-wide base rate. The same notebook always yields the same three facts — which is why the panel is labelled *"chosen by fixed rules · not AI."* Nothing is written or re-weighted by AI.

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

## Reading comfort

The header's **Aa** control opens a small popover for how the app *reads* — never what it says. Four choices, all persisted: **Theme** (Light, Dark, or a **Warm** low-blue palette for evening reading), **Text size** (four steps, scaling the whole app), **Line spacing**, and **Contrast** (which snaps to High automatically when your OS asks for more). Warm mode is a dedicated, hand-tuned palette measured to keep every text/surface pair above the WCAG AA 4.5:1 contrast floor — not a screen tint — so the forecasts stay legible. It's for comfort, not eye protection, and we don't claim otherwise.

## What moved (re-seals)

If a fixture is re-sealed, the newer forecast page shows a compact **what-moved** readout inside its "Re-sealed" note: each outcome's probability *was → now* with the change in whole points (▲/▼). Both numbers come from two immutable seals seen before kickoff — it's line movement between honest forecasts, not an edit, and no AI is involved. The three deltas always sum to zero.

## The heatmap (Expert)

The Expert view renders the sealed `score_matrix` as an accessible table: real row/column headers, tabular numerals, a per-cell screen-reader label, and the most-likely scoreline outlined and starred. The heat tint is mixed over the surface so cell text stays legible in light and dark themes, and all motion is CSS-only (so the global reduced-motion rule covers it). Its win/draw/loss totals reproduce the verdict bar exactly — that is [enforced on load](/Golavo/methodology/prediction/#exact-score-distribution--coherence). When the model family forecasts outcomes rather than goals, or the seal abstained, the heatmap is replaced by an honest "no exact-score distribution" note — never a fabricated grid.
