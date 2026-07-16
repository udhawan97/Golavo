---
title: AI providers & local models
description: How Golavo's optional AI layer works — local models, BYOK cloud, the evidence bundle, and the rules that stop AI from ever changing a probability.
---

AI in Golavo is **optional** and **additive**. Layer 0 — the deterministic forecast and cited facts — is the product, and it is fully local. AI absence changes nothing numeric.

:::caution[What AI does and does not do]
The AI layer **explains and cites** the forecast. It **does not improve forecast accuracy** and **cannot change, produce, or override a probability**. The deterministic engine owns every number; the AI is structurally prevented from stating one the engine did not produce. Turning AI off changes nothing about the numbers.
:::

**Status: implemented and off by default.** The safety machinery below is real and tested in CI with canned and adversarial responses (no live model). See the [implementation handoff](https://github.com/udhawan97/Golavo/blob/main/docs/handoff/codex-phase5.md) for exactly what is tested versus what needs a local model to exercise.

## The three layers

| Layer | What | Needs |
|---|---|---|
| **0 — Deterministic** | forecast + templated facts | nothing; always on, fully local |
| **1 — Local AI** | narrative & scenario text | [Ollama](https://docs.ollama.com/api/openai-compatibility) or [llama.cpp `llama-server`](https://github.com/ggml-org/llama.cpp/tree/master/tools/server); no key |
| **2 — Cloud AI (BYOK)** | guarded narrative | your own OpenAI or Anthropic key |

Local endpoints are OpenAI-compatible: Ollama at `http://localhost:11434/v1`, llama-server at `http://127.0.0.1:8080/v1`. llama-server is preferred where hard schema-constrained JSON is needed (it supports GBNF grammars and `json_schema`/`response_format`).

### The verdict and the deeper read

Every read opens with a one-line **verdict** — the engine's single most likely outcome, stated with its own probability (e.g. "Spain to win — 41.6%"). It is held to exactly the same rules as any claim: the number must be one the engine produced, or the verdict is dropped (never guessed). Below it, the read is instructed to **connect** the evidence — the reader already sees every fact and probability on screen, so the AI's value is in linking them (tensions between the models, corroborations, historical analogues), not restating a number in isolation.

### Fast and Deep

The read has two speeds, chosen with a toggle on the panel:

- **Fast** — a small model (e.g. `llama3.2`) writes a few grounded claims in seconds.
- **Deep analysis** — a bigger model (e.g. `gemma4:12b`) sees more of the evidence and writes a fuller synthesis — more claims, plus scenarios that connect facts to each other and surface tensions and corroborations. A 12B model on a rich match usually takes **5–8 minutes**; it reports **real staged progress** (assembling → researching → writing → verifying) with a live detail line and source counts, and you can cancel or drop back to Fast in one tap.

## Set up Ollama inside Golavo

The casual path requires no terminal commands:

1. Open **Settings → Local intelligence**. The guide remains visible while AI is
   **Off**, so setup does not depend on already knowing which provider to choose.
2. If Ollama is missing, choose **Download Ollama** to open the
   [official macOS download](https://ollama.com/download/mac). Move Ollama to
   Applications and open it once. Existing users can simply open Ollama and choose
   **Check again**. The [official macOS setup guide](https://docs.ollama.com/macos)
   is linked beside the installer.
3. Choose a recommended model inside Golavo:

   | Read | Recommended model | Approximate download | Intended use |
   |---|---|---:|---|
   | **Fast** | [`llama3.2:latest`](https://ollama.com/library/llama3.2) | 2.0 GB | short grounded read in seconds |
   | **Deep** | [`gemma4:12b-it-qat`](https://ollama.com/library/gemma4) | 7.2 GB | fuller evidence synthesis and scenarios |

Golavo asks its loopback sidecar to use Ollama's native pull API, then shows real
download status, transferred bytes, percentage, and **Cancel**. Only these curated
buttons may initiate a pull; arbitrary model names are not accepted by the download
route. A completed model is assigned to Fast or Deep and Local · Ollama is enabled.
If the model is already installed, the operation completes without downloading it
again.

The compact **Get or manage local models** guide on every Ollama analysis panel uses
the same status and controls. No download begins until you click. Ollama fetches model
layers from its registry and stores them locally; Golavo does not upload the evidence
bundle or match data during installation.

### Match research (separate opt-in)

Research is not an authoritative AI feed. Wikimedia discovery may suggest candidate pages
or entities. Golavo shows the source before fetching; capture begins only after you select
it. Permission is declared per host/path/method/content type in the source
registry. DuckDuckGo HTML scraping is disabled because it is too fragile and is not an
acceptable ingestion dependency.

Every extracted field must retain captured source text, URL, retrieval time and content
hash. A source-specific deterministic parser runs before optional **local** AI fallback.
AI cannot fill a missing value, and quote matching is exact. The result remains an untrusted
candidate and can only move into the local correction queue for your review. It never edits
the analysis, a source pack, a seal, training data, calibration, or settlement. HTTPS/DNS/IP,
redirect, size, time and hostile-markup guards fail closed. `GOLAVO_NO_RESEARCH=1` disables
the lane entirely.

Assign which installed model runs each mode in **Settings → Local intelligence** (auto-set to your smallest for Fast and largest for Deep). An "advanced" control on the panel lets you run any specific installed model for a single read.

### Which local model runs

Golavo probes the local server, lists installed models with their sizes, and — if you
do not use the recommended buttons or assign them yourself — uses the smallest for
Fast and the largest for Deep, skipping embedding-only models. To pin an exact model
outside the UI, set `GOLAVO_OLLAMA_MODEL` (or `GOLAVO_LLAMACPP_MODEL`). If the local
server is unreachable, has no models, or has no usable chat model, the panel names that
state and offers a real re-check path. Local models load their weights on first use, so
the first read is slower.

Under the hood, the Ollama path uses the native `/api/chat` structured-output endpoint (its `format` grammar reliably constrains **every** model to the schema, and disables "thinking" so a reasoning model doesn't burn minutes), the context window is sized to fit the (trimmed) prompt, and decoding is **enum-constrained** to the bundle's real citation ids — so the model can neither invent a source nor drop a number the engine didn't produce.

## The evidence bundle is all AI ever sees

AI receives a **MatchEvidenceBundle**: the sealed forecast, cited facts, typed features, source records, data-quality flags, and an explicit `allowed_numbers` list. It has no write path to probabilities. Selected research excerpts, when present, are fenced as untrusted source material and remain outside the engine evidence. The bundle is built deterministically from a sealed artifact (`golavo_core.evidence`) — the same artifact in yields the same bundle, byte-for-byte. Facts derived from goalscorer or shootout files carry per-file source ids (`<pack>#goalscorers` / `#shootouts`) rather than resolving to one generic pack.

## Hard rules

1. Output is schema-validated JSON (`verdict`, `claims`, `scenarios`, `candidate_facts`, and — when their lanes are on — `research_notes` and `background`). Local and OpenAI-compatible decoding is constrained to this schema (`response_format: json_schema`), so even a small local model returns the right shape rather than free-form prose. A claim whose number doesn't match the engine's exact display is dropped individually — its number is never shown — while the other verified claims stand. The verdict and the optional research/background lanes are reviewed separately, so a bad one is dropped without voiding the grounded claims.
2. **Numeric whitelist** — every numeric token must exactly match the trusted display of an `allowed_numbers` id referenced by that same claim. Units and references cannot be swapped; spelled, fractional, compound, and scientific notation fail closed. Any mismatch rejects the output (one retry, then Local-only fallback). Harmless extra keys a small model adds are pruned rather than failing the whole answer; the betting and credential scanners fold Unicode look-alikes and strip zero-width characters so obfuscated terms are still caught.
3. Claims without `source_ids` are dropped; numbered claims must cite one of the number's own trusted sources.
4. A betting-lexicon filter rejects "locks," "units," and odds formats.
5. Chain-of-thought is never exposed. Progress shows factual pipeline stages only (assembling evidence → model writing → verifying every number), reported by the sidecar rather than guessed.

## Research candidates enter correction review

Candidate facts are routed into the provenance-first correction queue with their source
receipt and immutable history. Local acceptance is a display annotation only. It does not
promote a value into a bundled source, verified match index, model feature, seal, calibration
row or settlement result. Upstream export is a separate user-triggered action and preserves
the source license namespace.

## Caching & privacy

Narrative caching also includes candidate-fact mode and a hash of sanitized optional context, so prompt-affecting input cannot reuse a stale result. Keys live in your OS keychain (or an environment variable in dev), are used only in a request header, and never touch the database, logs, cache, or exports. Cloud endpoints are fixed; local endpoint overrides are restricted to HTTP(S) loopback URLs so a BYOK header cannot be redirected.

Spend caps (`AI_PER_MATCH_CAP`, `AI_MONTHLY_CAP`) are reserved in configuration but **not yet enforced** — treat BYOK usage as opt-in and small. A hard cost meter is future work.

:::note[Status]
Implemented and **off by default**. The engine, ledger, and UI do not depend on it. See the [implementation handoff](https://github.com/udhawan97/Golavo/blob/main/docs/handoff/codex-phase5.md) and the [Roadmap](/Golavo/roadmap/).
:::
