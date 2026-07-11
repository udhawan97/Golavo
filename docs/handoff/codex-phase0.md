# Codex Phase 0 core handoff

- **Branch:** `lane/codex-core`
- **BASE_SHA:** `211637a`
- **Pinned martj42 upstream:** `ddd7249ac0c24c44a5bd8c3af1bf16fc971bebe9`
- **Canonical schema:** `ForecastArtifact` **0.1.0**
- **Phase 0 scope:** men's senior full internationals only

## What shipped

- Docs truth pass: current claims are Phase 0-only; desktop, updater, AI, BYOK,
  club coverage, and hash-chained ledger work are marked planned (ADR-0001).
- Vendored CC0-1.0 martj42 sourcepack with exact upstream pin, manifest, per-file
  SHA-256 digests, CC0 text, and CI provenance validation.
- Typed pandas/Parquet ingestion with dated former-name resolution, nullable
  scheduled fixtures, neutral-venue preservation, stable match ids, and a
  fail-loud training-cutoff invariant.
- Five deterministic candidates: climatological, Elo ordinal-logit, independent
  Poisson, time-decayed Dixon-Coles, and bivariate Poisson. Dixon-Coles `xi` is
  selected on pre-test validation only.
- Chronological WC2022, EURO2024, and WC2026 evaluation with log loss (primary),
  Brier, ECE, reliability bins with Wilson intervals, and RPS.
- Immutable seal/score CLI and `python -m golavo_core` entry point. Probability
  JSON is sorted and rounded to six decimals; the payload digest excludes only
  its self-referential `payload_sha256` field. Scoring writes a new artifact with
  `supersedes` and never mutates the seal.
- Read-only FastAPI routes with local Vite CORS and no source-mode auth.
- Eight deterministic synthetic contract fixtures spanning all four statuses,
  plus determinism, leakage, abstention, scoring, schema, provenance, and API tests.

## Evaluation

Lower is better. The WC2026 fold contains the **97 completed matches** available
in the pinned snapshot; three scheduled rows with null scores are excluded.

| Fold | Model | Log loss | Brier |
|---|---|---:|---:|
| WC2022 | climatological | 1.074249 | 0.651155 |
| WC2022 | elo_ordlogit | 1.015747 | 0.603744 |
| WC2022 | poisson_independent | 1.067719 | 0.642941 |
| WC2022 | dixon_coles | 1.064957 | 0.640144 |
| WC2022 | bivariate_poisson | 1.067719 | 0.642941 |
| EURO2024 | climatological | 1.142226 | 0.697113 |
| EURO2024 | elo_ordlogit | 1.030029 | 0.617385 |
| EURO2024 | poisson_independent | 1.022756 | 0.612261 |
| EURO2024 | dixon_coles | 0.997326 | 0.596576 |
| EURO2024 | bivariate_poisson | 1.022756 | 0.612261 |
| WC2026 | climatological | 1.056496 | 0.637083 |
| WC2026 | elo_ordlogit | 0.905550 | 0.531794 |
| WC2026 | poisson_independent | 0.959845 | 0.571654 |
| WC2026 | dixon_coles | 0.957076 | 0.570613 |
| WC2026 | bivariate_poisson | 0.959845 | 0.571654 |

Elo beats climatological on log loss on all three folds. No candidate is called
a champion. Dixon-Coles beats Elo on EURO2024; Elo is better on both World Cup
folds. Full ECE, RPS, parameters, and reliability bins are in
`docs/handoff/eval_summary.json`; the readable table is in `eval_report.md`.

## Contract and fixtures

- Schema: `docs/contracts/forecast_artifact.schema.json`
- Sample artifacts: `data/fixtures/sample_artifacts/fa_*.json`
- Sample statuses: 3 sealed, 2 scored, 2 abstained, 1 voided
- Small CC0 parser subset: `data/fixtures/martj42-results-subset.csv`

The sample artifacts are explicitly synthetic integration fixtures, not claims
about historical forecasts. Their `code_git_sha` sentinel is `0000000` for that
reason. Runtime-created artifacts resolve the checked-out Git SHA.

## API routes

- `GET /health`
- `GET /api/v1/forecasts` — all artifact JSON, newest first
- `GET /api/v1/forecasts/{artifact_id}`
- `GET /api/v1/eval/summary`

CORS allows `http://127.0.0.1:5173` and `http://localhost:5173`. There is no auth
in Phase 0 source mode.

## Known gaps

- martj42 supplies match dates, not kickoff times. Phase 0 represents kickoff as
  `00:00:00Z`; seals must therefore use an earlier timestamp. This is explicit in
  the evaluation report and must be replaced if a lawful kickoff-time source lands.
- WC2026 is still in progress in the pinned snapshot. The fold is a partial-window
  report and must be regenerated from a newly pinned pack after completion.
- Bivariate Poisson's shared component changes exact-score correlation, but shared
  goals cancel in the 1X2 goal difference; its Phase 0 1X2 scores therefore match
  independent Poisson. Exact-score evaluation is out of scope.
- The artifact audit is append-only JSONL but not hash-chained. Cross-artifact
  chaining is planned for Phase 1 (ADR-0001).
- No accepted source exists in Phase 0 for club results, lineups, injuries,
  corners, shots, cards, or xG. Rejected provenance-laundering datasets have no adapters.
- Source mode is read-only and unauthenticated by design. Desktop sidecar tokens,
  signed packs/updates, keychain storage, AI, and UI integration are later phases.
