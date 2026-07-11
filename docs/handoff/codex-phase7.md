# Phase 7 handoff — Fact & Coincidence engine (the Commentator's Notebook)

**Base SHA:** `4078135` (v0.1.0 tagged; tree clean at start).
**Lane:** `lane/phase7`, landed on `main` in three verified merges.
**Reviewer:** Codex.

The goal was a deterministic, source-backed Fact & Coincidence engine over the vendored CC0
packs where **a coincidence never masquerades as evidence, and a fact never changes a number** —
enforced by a machine-checked invariant, not discipline.

## What shipped

- `core/golavo_core/facts/` — the engine (registry, templates, guardrails, engine, evidence
  adapter, invariant).
- `docs/contracts/facts.schema.json` — the `CommentatorsNotebook` contract (new, additive).
- `core/golavo_core/evidence.py` — additive `extra_facts`/`extra_numbers` params on
  `build_evidence_bundle` (default output byte-identical to before).
- `golavo notebook` CLI command; `GET /api/v1/forecasts/{id}/facts`; the narrative endpoint folds
  the notebook into the AI bundle.
- UI `CommentatorsNotebook` panel on `ForecastDetail`, additive contract types, fetch + mock.
- Demo data: a real France v Morocco seal + notebook (`scripts/generate_notebook_demo.py`).
- Tests: `core/tests/test_phase7_facts.py` (21), `server/tests/test_phase7_facts_api.py` (4).
- Docs: `docs-site/.../methodology/facts.md`; matchday + README + CHANGELOG updated.

## The template catalogue

Fixed, pre-registered family. `arity` = hypotheses per match (2 = once per side, 1 = h2h /
competition). `min_sample` is the floor a candidate must clear; `staleness` auto-hides form facts
whose last contributing match is older than the window (`none` = structural, all-time).

| Template | Label | Scope | Arity | Min sample | Staleness | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `unbeaten_run` | context | team | 2 | 3 | 400 d | results |
| `winless_run` | context | team | 2 | 3 | 400 d | results |
| `win_streak` | context | team | 2 | 3 | 400 d | results |
| `clean_sheet_run` | context | team | 2 | 3 | 400 d | results |
| `home_away_form` | context | team | 2 | 5 | 400 d | results |
| `biggest_win` | context | team | 2 | 10 | none | results |
| `head_to_head_record` | context | head-to-head | 1 | 3 | 12 y | results |
| `neutral_venue_record` | context | team | 2 | 5 | none | results |
| `top_scorer` | context | team | 2 | 10 | none | goalscorers (internationals only) |
| `shootout_record` | context | team | 2 | 3 | none | shootouts (internationals only) |
| `home_advantage_base_rate` | predictive | competition | 1 | 100 | none | results |
| `competition_debut_base_rate` | predictive | competition | 1 | 200 | none | results |
| `day_of_week_streak` | coincidence | team | 2 | 4 | 400 d | results |
| `scoreline_repeat` | coincidence | head-to-head | 1 | 2 | none | results |
| `calendar_date_repeat` | coincidence | team | 2 | 3 | none | results |

## The multiple-comparison bound

`family_size()` = Σ arity = **26** hypotheses evaluated per match. It is a constant of the
registry, **not a function of the data** — the engine cannot widen its search until something looks
significant. `REGISTRY_VERSION = "2026.07.11"`; adding/removing/re-labelling a template bumps it and
is a reviewed, logged change. Coincidences are ranked by a deterministic **specificity** score, not
by any significance test, and are capped at 3. Predictive facts are labelled but **never applied to
the model** — the engine takes signal only through its own typed-feature gate.

## The no-write invariant (design)

Two machine checks, both exercised by tests (`test_phase7_facts.py`):

1. **Isolation (static)** — `assert_facts_isolated()` AST-parses every module in the facts package
   and asserts none imports `golavo_core.models`, `.calibration`, `.evaluation`, or `.artifacts`
   (the forecast/probability/calibration writers). No code path *can* reach a writer. The package's
   only `golavo_core` imports are readers/adapters: `ingest` (indirectly via callers), `resources`
   (schema path), `ai.whitelist` (a pure text scanner, in the evidence adapter).
2. **Immutability (runtime)** — `verify_notebook_pipeline_pure(artifact, matches, …)` deep-copies a
   real sealed artifact, runs the full notebook + AI-fold pipeline, and asserts (a) the artifact's
   `forecast`/`evaluation` bytes are unchanged, and (b) folding notebook facts into an evidence
   bundle only *appends* — every engine number keeps its exact id/value/display, and every folded
   number is `nb_`-namespaced (a collision is rejected by `validate_evidence_bundle`).

Number discipline (`assert_number_discipline`) is the third supporting guard: every digit token in a
fact's text must equal one of the fact's declared `numbers` displays (the regex is byte-identical to
the AI whitelist's), which is what lets a fact fold verbatim into `allowed_numbers`. Dates carry
digits that are not claims, so facts keep calendar dates in `date_range` only, never in `text`.

## AI fold

`notebook_to_evidence(notebook)` converts context+predictive facts (never coincidences, and never
betting-lexicon text) into evidence-bundle `facts` (kind `context`) + `allowed_numbers` (namespaced
`nb_*`). The evidence contract is **unchanged** — no schema edit was needed. The narrative endpoint
loads the sibling notebook and passes these through the additive params; the numeric whitelist still
governs, so the model may cite a notebook fact but cannot invent one.

## Server / storage model

Notebooks are **precomputed** next to artifacts at `notebooks/<artifact_id>.json` (a subdir, so they
never match the `fa_*.json` artifact glob) by `golavo notebook`. The endpoint is read-only and
pack-free; with no precomputed notebook it returns an honest `{available:false, notebook:null}`
envelope rather than fabricating facts.

## UI verification (live)

Verified in the running dev workbench (mock mode), no console errors, on the committed demo
artifact `fa_b44892255616a50d59bb` (route `#/forecast/fa_b44892255616a50d59bb`). To reproduce:
`npm --prefix ui run dev`, open that route. The demo is the real **France v Morocco** FIFA World Cup
fixture (neutral venue, Foxborough), sealed as-of 2026-07-08 from the retained martj42 snapshot.

Rendered (abridged), grouped by label with sample / base rate / source / freshness chips:

- **Predictive** — "In FIFA World Cup, the home side has won 61.2% of 134 non-neutral matches…"
  (sample 134, base rate 61.2%); "…teams in their first year after arriving have won 26.3% of 240
  matches (across 73 first-time teams)…".
- **Context** — biggest wins (14–0 / 7–0), Morocco unbeaten in 43, H2H France 4–2–0, home/away form,
  France win streak, neutral-venue records (54.2% / 46.8% — relevant for this neutral fixture).
- **Coincidence** (quarantined, dashed block, "For the pub, not the forecast — capped at 3, never
  shown to the AI") — "France have played on this calendar date 3 times before, winning 0."
- **Footer** — "26 pre-registered hypotheses · registry 2026.07.11 · 1 candidate suppressed · as of
  2026-07-08."

A synthetic artifact (no notebook) renders the honest **"No notebook for this fixture"** empty state.

> Screenshots: the committed `ui/screenshots/*.png` predate this panel. No headless capture tooling
> is installed and the browser tool cannot write PNGs to disk, so the panel is verified live via the
> route above rather than by a new committed PNG. A follow-up can add `10-notebook-dark.png` once a
> capture step exists.

## Honest gaps & judgement calls

- **Internationals-only scorers/shootouts.** Only the martj42 pack ships goalscorers and shootouts;
  the openfootball league packs ship results only. `top_scorer`/`shootout_record` therefore do not
  run for club fixtures. **No club scorer, assist, or lineup fact is fabricated.**
- **"Promoted team" → debut-window proxy.** The CC0 single-league packs carry no division tier, so a
  real promotion cannot be detected. `competition_debut_base_rate` reports the first-year win rate of
  teams that *first appear mid-dataset* (teams present from the first season are excluded as
  left-censored) and is labelled as exactly that — never as "promoted." (EPL pack: 25.6% across 14
  such teams — a realistic newly-arrived-team base rate.)
- **Forward-test data artifact.** The retained martj42 snapshot carries speculative fixtures through
  2026, so e.g. "Morocco unbeaten in 43" is faithful to the pinned pack (their last loss in the pack
  is 2024-01-30), not a bug. Facts mirror the byte-pinned pack exactly.
- **`top_scorer` names a player only in `values`, not in the whitelist-safe `text`** (a player name
  is digit-free in practice, but opponent/club names can carry digits, e.g. "Schalke 04", so no
  historical opponent/player name goes into AI-facing text; the UI reads them from `values`).
- **Facts are precomputed, not computed on request** — the server stays read-only and pack-free, and
  the desktop ledger ships empty, so notebooks appear only where `golavo notebook` has written one.
- **AI evidence schema unchanged.** Folded notebook facts use the existing `kind: "context"`; the
  predictive/context/coincidence distinction lives in the notebook contract and the UI, so the AI
  contract needed no (even additive) edit.

## Reproduce

```bash
python -m venv .venv && . .venv/bin/activate && pip install -e "core[dev]" -e "server[dev]" ruff
ruff check core server scripts
python -m pytest core/tests server/tests -q
python scripts/validate_provenance.py
python scripts/generate_notebook_demo.py          # regenerates the demo (deterministic; no diff)
( cd ui && npm ci && npm run build )
```
