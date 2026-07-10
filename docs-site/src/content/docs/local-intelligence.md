---
title: Local Intelligence
description: Golavo's deterministic engine is the product, not a downgraded fallback. AI is optional on top.
---

**Local Intelligence is not a downgraded mode.** Golavo's deterministic statistical engine — the models described in the [methodology](/Golavo/methodology/prediction/) — produces the entire forecast locally, with no network and no AI. It is the product.

## What runs locally

- The full W/D/L forecast, exact-score matrix, and (where data allows) scorers and corners.
- The cited fact and coincidence engine.
- The sealed ledger and after-the-whistle scoring.

All of it computes on your machine over data you've already synced. Staleness is always shown.

## What is optional on top

- **Local AI** (Ollama / llama.cpp) for narrative — no key, no cloud.
- **Cloud AI** (your own OpenAI/Anthropic key) for narrative and research.

Turning AI off changes nothing about the numbers. See [AI providers](/Golavo/ai/providers/).

## What "local" does not mean

Local means local *computation* over *cached* data. It does not mean magically current offline data — the latest results still have to be synced when you have a network. Golavo always shows how fresh its data is.
