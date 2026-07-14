---
title: Local Intelligence
description: Golavo's deterministic engine is the product, not a downgraded fallback. AI is optional on top.
---

**Local Intelligence is not a downgraded mode.** Golavo's deterministic statistical engine — the models described in the [methodology](/Golavo/methodology/prediction/) — produces the entire forecast locally, with no network and no AI. It is the product.

## What runs locally

- The full W/D/L forecast and exact-score matrix. (Scorers and corners are planned — no accepted open source supplies them yet.)
- The deterministic evidence bundle that cites every engine number.
- The sealed ledger and after-the-whistle scoring.

All of it computes on your machine over data you've already synced. Staleness is always shown.

## What is optional on top

- **Local AI** (Ollama / llama.cpp) for narrative — no key, no cloud.
- **Cloud AI** (your own OpenAI/Anthropic key) for narrative and research.

AI is **off by default**. Enable it in **Settings → Local intelligence** by choosing a provider (local Ollama or llama.cpp, or your own OpenAI/Anthropic key); an **AI Deep Read** panel then appears, recessed, on forecast pages. It only reads and cites the numbers the deterministic engine already produced — it cannot change a probability and does not improve accuracy. Turning AI off changes nothing about the numbers. See [AI providers](/Golavo/ai/providers/).

For Ollama, you do not need to begin in a terminal. The setup guide is visible in
Settings even while AI is Off and is also available beside the match analysis controls.
It checks whether Ollama is running, links to the official installer, offers the
recommended Fast and Deep models, and shows real download progress with cancellation.
Choosing a model enables Local · Ollama and assigns it to the matching read. Nothing is
downloaded automatically. See [Set up Ollama inside Golavo](/Golavo/ai/providers/#set-up-ollama-inside-golavo).

## What "local" does not mean

Local means local *computation* over *cached* data. It does not mean magically current offline data — the latest results still have to be synced when you have a network. Golavo always shows how fresh its data is.
