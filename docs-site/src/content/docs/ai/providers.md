---
title: AI providers & local models
description: How Golavo's optional AI layer works — local models, BYOK cloud, the evidence bundle, and the rules that stop AI from ever changing a probability.
---

AI in Golavo is **optional** and **additive**. Layer 0 — the deterministic forecast and cited facts — is the product, and it is fully local. AI absence changes nothing numeric.

:::caution[What AI does and does not do]
The AI layer **explains and cites** the forecast. It **does not improve forecast accuracy** and **cannot change, produce, or override a probability**. The deterministic engine owns every number; the AI is structurally prevented from stating one the engine did not produce. Turning AI off changes nothing about the numbers.
:::

**Status: implemented in Phase 5, off by default.** The safety machinery below is real and tested in CI with canned and adversarial responses (no live model). See the [Phase 5 handoff](https://github.com/udhawan97/Golavo/blob/main/docs/handoff/codex-phase5.md) for exactly what is tested versus what needs a local model to exercise.

## The three layers

| Layer | What | Needs |
|---|---|---|
| **0 — Deterministic** | forecast + templated facts | nothing; always on, fully local |
| **1 — Local AI** | narrative & scenario text | [Ollama](https://docs.ollama.com/api/openai-compatibility) or [llama.cpp `llama-server`](https://github.com/ggml-org/llama.cpp/tree/master/tools/server); no key |
| **2 — Cloud AI (BYOK)** | narrative & research | your own OpenAI or Anthropic key |

Local endpoints are OpenAI-compatible: Ollama at `http://localhost:11434/v1`, llama-server at `http://127.0.0.1:8080/v1`. llama-server is preferred where hard schema-constrained JSON is needed (it supports GBNF grammars and `json_schema`/`response_format`).

## The evidence bundle is all AI ever sees

AI receives a **MatchEvidenceBundle**: the sealed forecast, cited facts, typed features, source records, data-quality flags, and an explicit `allowed_numbers` list. It has no access to the internet by default and no write path to probabilities. The bundle is built deterministically from a sealed artifact (`golavo_core.evidence`) — the same artifact in yields the same bundle, byte-for-byte.

## Hard rules

1. Output is schema-validated JSON (`claims`, `scenarios`, `candidate_facts`).
2. **Numeric whitelist** — every number in the output must resolve to an `allowed_numbers` id, or the output is rejected (one retry, then Local-only fallback).
3. Claims without `source_ids` are dropped.
4. A betting-lexicon filter rejects "locks," "units," and odds formats.
5. Chain-of-thought is never exposed. The analysis animation shows factual pipeline stages only (snapshot → features → model → seal).

## Confirmed facts become typed features (planned)

The intended design: if AI research confirms a fact (allowlisted sources only, with quote-match verification and **your** confirmation), it becomes a typed feature, the statistical model **reruns**, and the UI shows the delta. Silent adjustment is structurally impossible — and even here, the AI never writes a number; it proposes a fact you must confirm.

As of Phase 5 the *guard* for this exists and is default-off: a model may emit `candidate_facts`, and any number they assert must be grounded verbatim in the cited quote or it is rejected. The full ingestion loop (confirm → typed feature → rerun → delta) is not yet built.

## Caching & privacy

Narrative is cached by `(bundle_hash, provider, model, prompt_version)`. Keys live in your OS keychain (or an environment variable in dev), are used only in a request header, and never touch the database, logs, cache, or exports.

Spend caps (`AI_PER_MATCH_CAP`, `AI_MONTHLY_CAP`) are reserved in configuration but **not yet enforced** — treat BYOK usage as opt-in and small. A hard cost meter is future work.

:::note[Status]
Implemented in Phase 5 and **off by default**. The engine, ledger, and UI do not depend on it. See the [Phase 5 handoff](https://github.com/udhawan97/Golavo/blob/main/docs/handoff/codex-phase5.md) and the [Roadmap](/Golavo/roadmap/).
:::
