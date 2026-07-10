---
title: AI providers & local models
description: How Golavo's optional AI layer works — local models, BYOK cloud, the evidence bundle, and the rules that stop AI from ever changing a probability.
---

AI in Golavo is **optional** and **additive**. Layer 0 — the deterministic forecast and cited facts — is the product, and it is fully local. AI absence changes nothing numeric.

## The three layers

| Layer | What | Needs |
|---|---|---|
| **0 — Deterministic** | forecast + templated facts | nothing; always on, fully local |
| **1 — Local AI** | narrative & scenario text | [Ollama](https://docs.ollama.com/api/openai-compatibility) or [llama.cpp `llama-server`](https://github.com/ggml-org/llama.cpp/tree/master/tools/server); no key |
| **2 — Cloud AI (BYOK)** | narrative & research | your own OpenAI or Anthropic key |

Local endpoints are OpenAI-compatible: Ollama at `http://localhost:11434/v1`, llama-server at `http://127.0.0.1:8080/v1`. llama-server is preferred where hard schema-constrained JSON is needed (it supports GBNF grammars and `json_schema`/`response_format`).

## The evidence bundle is all AI ever sees

AI receives a **MatchEvidenceBundle**: the sealed forecast, cited facts, typed features, source records, data-quality flags, and an explicit `allowed_numbers` list. It has no access to the internet by default and no write path to probabilities.

## Hard rules

1. Output is schema-validated JSON (`claims`, `scenarios`, `candidate_facts`).
2. **Numeric whitelist** — every number in the output must resolve to an `allowed_numbers` id, or the output is rejected (one retry, then Local-only fallback).
3. Claims without `source_ids` are dropped.
4. A betting-lexicon filter rejects "locks," "units," and odds formats.
5. Chain-of-thought is never exposed. The analysis animation shows factual pipeline stages only (snapshot → features → model → seal).

## Confirmed facts become typed features

If AI research confirms a fact (allowlisted sources only, with quote-match verification and **your** confirmation), it becomes a typed feature, the statistical model **reruns**, and the UI shows the delta. Silent adjustment is structurally impossible.

## Spend, caching, privacy

Cloud calls show a token estimate first and honor per-match and monthly caps (defaults $0.05/match, $5/month). Narrative is cached by `(bundle_hash, provider, model, prompt_version)`. Keys live in your OS keychain, never in the database, logs, or exports.

:::note[Status]
The AI layer arrives in Phase 6, after the engine, ledger, and UI. See the [Roadmap](/Golavo/roadmap/).
:::
