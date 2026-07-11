# Golavo Phase 1 core handoff (English Premier League, historical)

- **Base:** `main` @ `b05127f`
- **Pinned openfootball upstream:** `a5dd38b3bcbe3aa2477cf400f569264253d51431` (committed 2026-05-30)
- **Canonical schema:** `ForecastArtifact` 0.1.0. The only change is `EvalSummary.fold_id`,
  widened from a fixed enum to a pattern — backward-compatible (WC/EURO ids still match),
  and the UI-facing `ForecastArtifact` contract is untouched.
- **Phase 1 scope:** add ONE club competition — the English Premier League — **historical only**.

## The gate (openfootball audit)

Verdict **ACCEPT_HISTORICAL**. 15 clean seasons (2010-11 → 2024-25), each a complete 380-match
double round-robin (20 teams, 19 home + 19 away each, no self-matches, no duplicate ordered
pairs). The partial **2025-26** capture is **excluded**: 27 results were absent at the
2026-05-30 snapshot and encoded as a divergent `[0, 0]` list (seen in no other season,
uniformly zero) — treated as INCOMPLETE, never fabricated as a real 0-0. Live in-season
updating is UNVERIFIED until 2026-27; independent second-source cross-checking is DEFERRED
(footballcsv is stale to ~2020/21 with divergent names). Report:
`docs/handoff/openfootball-audit.{md,json}`.

## What shipped

- `packs/openfootball-eng-pl/`: pinned PL season JSON (16 files) + CC0 text + a manifest with
  per-file SHA-256. Built by `scripts/build_openfootball_pack.py`.
- **Source-agnostic ingestion**: `load_matches(pack)` dispatches on manifest `source_id`;
  `load_openfootball_table` produces the same canonical typed table as martj42. Team-name drift
  is canonicalized (`Arsenal FC` → `Arsenal`, `AFC Bournemouth` → `Bournemouth`); `[0, 0]`
  list scores become `is_complete = False`.
- **Chronological EPL evaluation** (`evaluate_club` / `golavo evaluate-club`) reusing the five
  candidates unchanged: `docs/handoff/eval_report_epl.md` + `eval_summary_epl.json`.
- `seal`/`score` are now source-agnostic via the dispatcher (Phase 0 internationals seals are
  unaffected; see gaps for why no club seal is produced).
- **Combined eval API**: `GET /api/v1/eval/summary` merges international + club folds.
- `scripts/validate_provenance.py` validates every pack; a scoped ruff `E501` ignore covers the
  Markdown-report generator only.
- Tests: `core/tests/test_phase1.py` (canonicalization, loader schema/counts, dispatcher, audit
  verdict, club-eval gate + schema validation).

## Evaluation (English Premier League; log loss primary, lower is better)

| Fold | Model | Log loss | Brier |
|---|---|---:|---:|
| EPL2022-23 | climatological | 1.049541 | 0.632828 |
| EPL2022-23 | elo_ordlogit | 1.006378 | 0.600932 |
| EPL2022-23 | poisson_independent | 1.024987 | 0.613954 |
| EPL2022-23 | dixon_coles | 1.027237 | 0.614652 |
| EPL2022-23 | bivariate_poisson | 1.024987 | 0.613954 |
| EPL2023-24 | climatological | 1.055077 | 0.637613 |
| EPL2023-24 | elo_ordlogit | 0.963359 | 0.570622 |
| EPL2023-24 | poisson_independent | 0.949398 | 0.560502 |
| EPL2023-24 | dixon_coles | 0.958672 | 0.567280 |
| EPL2023-24 | bivariate_poisson | 0.949398 | 0.560502 |
| EPL2024-25 | climatological | 1.082152 | 0.656510 |
| EPL2024-25 | elo_ordlogit | 1.007546 | 0.602476 |
| EPL2024-25 | poisson_independent | 1.045107 | 0.629649 |
| EPL2024-25 | dixon_coles | 1.045201 | 0.629177 |
| EPL2024-25 | bivariate_poisson | 1.045107 | 0.629649 |

Every candidate beats the climatological baseline on log loss on all three folds (the Phase 1
gate). Elo wins 2022-23 and 2024-25; independent/bivariate Poisson win 2023-24. Dixon-Coles ≈
independent Poisson (tuned decay near zero). No model is crowned a champion.

## Known gaps

- **No live club seal.** openfootball is historical; a seal requires `as_of` **after** the
  snapshot was retrieved and **before** kickoff — which no already-played PL match can satisfy.
  A real forward club seal awaits live-season data. This is honest, not a defect.
- openfootball kickoff times are venue-local and used as-is for the historical pack.
- 2025-26 is excluded; regenerate from a clean re-pin once the season is fully captured.
- Lineups, injuries, corners, shots, cards, and xG still have **no accepted open source**.
- Live in-season updating unverified; the audit trail remains append-only JSONL (hash chaining
  deferred, ADR-0001).
