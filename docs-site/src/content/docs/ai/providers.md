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

### The verdict and the deeper read

Every read opens with a one-line **verdict** — the engine's single most likely outcome, stated with its own probability (e.g. "Spain to win — 41.6%"). It is held to exactly the same rules as any claim: the number must be one the engine produced, or the verdict is dropped (never guessed). Below it, the read is instructed to **connect** the evidence — the reader already sees every fact and probability on screen, so the AI's value is in linking them (tensions between the models, corroborations, historical analogues), not restating a number in isolation.

### Fast and Deep

The read has two speeds, chosen with a toggle on the panel:

- **Fast** — a small model (e.g. `llama3.2`) writes a few grounded claims in seconds.
- **Deep analysis** — a bigger model (e.g. `gemma4:12b`) sees more of the evidence and writes a fuller synthesis — more claims, plus scenarios that connect facts to each other and surface tensions and corroborations. A 12B model on a rich match usually takes **5–8 minutes**; it reports **real staged progress** (assembling → researching → writing → verifying) with a live detail line and source counts, and you can cancel or drop back to Fast in one tap.

### Web research (opt-in)

Off by default, and the **only** setting that lets Golavo reach the general web. With "Let the AI research on the web" enabled in Settings, a read fetches a few **Wikipedia** pages and a **web search** for the fixture and adds a clearly-separated **"Analyst research"** section. That lane is badged **not engine-verified**: each finding must quote its fetched page **verbatim** (checked after fetching), its `source_url` must be one of the URLs actually fetched, and any number in it is checked against that quote — never rescued by an engine number. A failed or paraphrased note is dropped; a bad research lane can never void the grounded read. Fetches are https-only against a fixed host allowlist (`en.wikipedia.org`, DuckDuckGo's keyless HTML endpoints) with a proper User-Agent; web search is best-effort and falls back to Wikipedia-only when it is unavailable. The `GOLAVO_NO_RESEARCH=1` kill switch disables all of it (set in CI).

Assign which installed model runs each mode in **Settings → Local intelligence** (auto-set to your smallest for Fast and largest for Deep). An "advanced" control on the panel lets you run any specific installed model for a single read.

### Which local model runs

You don't have to pull a specific model. Golavo probes the local server, lists your installed models with their sizes, and — if you don't assign them yourself — uses the smallest for Fast and the largest for Deep, skipping embedding-only models. To pin an exact model outside the UI, set `GOLAVO_OLLAMA_MODEL` (or `GOLAVO_LLAMACPP_MODEL`). If the local server is unreachable or has no usable model, the panel says so plainly — start the server or pull a model, then retry. Local models load their weights on first use, so the first read is slower.

Under the hood, the Ollama path uses the native `/api/chat` structured-output endpoint (its `format` grammar reliably constrains **every** model to the schema, and disables "thinking" so a reasoning model doesn't burn minutes), the context window is sized to fit the (trimmed) prompt, and decoding is **enum-constrained** to the bundle's real citation ids — so the model can neither invent a source nor drop a number the engine didn't produce.

## The evidence bundle is all AI ever sees

AI receives a **MatchEvidenceBundle**: the sealed forecast, cited facts, typed features, source records, data-quality flags, and an explicit `allowed_numbers` list. It has no write path to probabilities, and no access to the internet unless you turn on web research (above) — in which case fetched pages are fed to it strictly as fenced *untrusted data* that can never change a number. The bundle is built deterministically from a sealed artifact (`golavo_core.evidence`) — the same artifact in yields the same bundle, byte-for-byte. Facts derived from the goalscorer or shootout data now carry a per-file source id (`<pack>#goalscorers` / `#shootouts`) so the read's citations are attributed distinctly rather than all resolving to one "data pack".

## Hard rules

1. Output is schema-validated JSON (`verdict`, `claims`, `scenarios`, `candidate_facts`, and — when their lanes are on — `research_notes` and `background`). Local and OpenAI-compatible decoding is constrained to this schema (`response_format: json_schema`), so even a small local model returns the right shape rather than free-form prose. A claim whose number doesn't match the engine's exact display is dropped individually — its number is never shown — while the other verified claims stand. The verdict and the optional research/background lanes are reviewed separately, so a bad one is dropped without voiding the grounded claims.
2. **Numeric whitelist** — every numeric token must exactly match the trusted display of an `allowed_numbers` id referenced by that same claim. Units and references cannot be swapped; spelled, fractional, compound, and scientific notation fail closed. Any mismatch rejects the output (one retry, then Local-only fallback). Harmless extra keys a small model adds are pruned rather than failing the whole answer; the betting and credential scanners fold Unicode look-alikes and strip zero-width characters so obfuscated terms are still caught.
3. Claims without `source_ids` are dropped; numbered claims must cite one of the number's own trusted sources.
4. A betting-lexicon filter rejects "locks," "units," and odds formats.
5. Chain-of-thought is never exposed. The progress animation shows factual pipeline stages only (assembling evidence → researching the web → the model writing → verifying every number), reported by the sidecar rather than guessed.

## Confirmed facts become typed features (planned)

The intended design: if AI research confirms a fact (allowlisted sources only, with quote-match verification and **your** confirmation), it becomes a typed feature, the statistical model **reruns**, and the UI shows the delta. Silent adjustment is structurally impossible — and even here, the AI never writes a number; it proposes a fact you must confirm.

As of Phase 5 the *guard* for this exists and is default-off: a model may emit `candidate_facts`, and any number they assert must be grounded verbatim in the cited quote or it is rejected. The full ingestion loop (confirm → typed feature → rerun → delta) is not yet built.

## Caching & privacy

Narrative caching also includes candidate-fact mode and a hash of sanitized optional context, so prompt-affecting input cannot reuse a stale result. Keys live in your OS keychain (or an environment variable in dev), are used only in a request header, and never touch the database, logs, cache, or exports. Cloud endpoints are fixed; local endpoint overrides are restricted to HTTP(S) loopback URLs so a BYOK header cannot be redirected.

Spend caps (`AI_PER_MATCH_CAP`, `AI_MONTHLY_CAP`) are reserved in configuration but **not yet enforced** — treat BYOK usage as opt-in and small. A hard cost meter is future work.

:::note[Status]
Implemented in Phase 5 and **off by default**. The engine, ledger, and UI do not depend on it. See the [Phase 5 handoff](https://github.com/udhawan97/Golavo/blob/main/docs/handoff/codex-phase5.md) and the [Roadmap](/Golavo/roadmap/).
:::
