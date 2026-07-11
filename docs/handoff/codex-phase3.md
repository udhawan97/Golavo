# Golavo Phase 3 core handoff (forward sealed-forecast loop, internationals)

- **Base:** `main` @ `1c92347`. Landed in three verified checkpoints: `6a5539c`
  (retention + anchored loop + tests), `b251832` (calibration record + API + Ledger UI),
  and the docs/live-seal commit that carries this handoff. Each checkpoint was pushed to
  `origin/main` only after ruff + full pytest + provenance-for-all-packs + `ui npm run
  build` passed twice.
- **Phase 3 scope:** the product's core thesis, for **internationals only** — seal a REAL
  upcoming fixture before kickoff, score it after full time from a later snapshot, and
  surface the real sealed→scored calibration record. The openfootball club packs are
  season-lagged captures with no verified live cadence, so a **club forward loop is an
  explicit non-goal**; club coverage remains historical backtesting.
- **Canonical schema:** `ForecastArtifact` bumped 0.1.0 → **0.2.0, additive and
  backward-compatible** (`schema_version` is now an enum accepting both; every 0.1.0
  artifact still validates). New: optional `Snapshot.upstream_committed_at_utc`, optional
  top-level `void_reason`, shared `ActualResult`/`ScoreMetrics` defs, and the new
  `CalibrationSummary`/`CalibrationChain` contracts. The UI contract mirror accepts both
  versions.

## Retained snapshots + registry

| Pack | Upstream ref | Upstream committed | Retrieved | Files |
|---|---|---|---|---|
| `packs/martj42-internationals` (T1) | `ddd7249ac0c24c44a5bd8c3af1bf16fc971bebe9` | (not recorded — pre-anchor pack, manifest untouched) | 2026-07-10T19:35:25Z | full |
| `packs/martj42-internationals-273c731492df` (T0) | `273c731492df960cae363317e8e78e2be4b4b7cf` | 2026-07-07T23:01:13Z | 2026-07-11T04:36:22Z | core (`results.csv`, `former_names.csv`, license) |

`packs/snapshots.json` registers every vendored pack (both martj42 snapshots and the
five openfootball packs) as `{pack, source_id, upstream_ref, upstream_committed_at_utc,
retrieved_at_utc, manifest_sha256}`. Registry entries and pack directories are
append-only: `build_sourcepack.py` refuses to re-fetch a registered ref, refuses to
write into an existing directory, and refuses to rewrite an existing entry;
`validate_provenance.py` (no args) discovers every `packs/*/manifest.json`, verifies
every declared byte, and cross-checks the registry — CI runs exactly that. The Phase 0
pack's manifest was deliberately left byte-identical (the six committed eval summaries
embed its manifest sha256).

## Anchor semantics (the honest core of the loop)

Any snapshot fetched today gets `retrieved_at_utc` = today, which would make a
CI-reproducible "seal in the past, score from the newer pack" test impossible under the
old `as_of ≥ retrieved_at` rule. Phase 3 anchors validity on the time the pinned data
state **verifiably existed publicly**: the upstream ref's commit time, recorded by the
builder from the GitHub commits API as `upstream_committed_at_utc`, with our retrieval
time as the fallback for packs that predate the anchor. Both timestamps are recorded
honestly; nothing is backdated. Seal requires `anchor ≤ as_of < kickoff` (day proxy) and
refuses fixtures that already carry a result in the sealing snapshot; score requires the
newer snapshot's anchor to be strictly greater than the seal's and stamps
`scored_at_utc` from it (deterministic — no wall clock anywhere in artifact bytes).

Caveats stated plainly: the upstream commit time is upstream-asserted metadata (a
committer can forge dates), and deterministic artifacts cannot themselves prove when
they were created. The trust anchor for *forwardness* is **publication**: a genuine seal
is committed and pushed to this public repository before the fixture's day-proxy
kickoff; git history is the evidence. Mechanically-retrospective seals exist only inside
tests (tmp dirs) and are never published as forecasts.

## The reproducible forward-loop test (task 4, the crux)

`core/tests/test_phase3.py` (14 tests) replays the loop offline from the two retained
packs: **France v Morocco, 2026-07-09** is scheduled (NA) at T0 and completed **2–0** at
T1 with byte-identical identity fields (same `match_id`). The test seals at
`as_of = 2026-07-08T00:00:00Z` (T-24h against the 00:00 UTC day proxy; 59 min after T0's
upstream commit), scores from T1, and asserts: byte-identical seal and scored artifacts
across reruns, correct outcome (home) and metrics (log loss = −ln p_home, Brier
recomputed), an intact `supersedes` chain, unchanged seal bytes after scoring, and every
invariant's failure mode (as_of before the anchor, at/after kickoff, already-completed
fixture, same-snapshot scoring, still-scheduled scoring). The postpone path: Spain v
Belgium (scheduled at T0, still scheduled at T1) cannot be scored; voiding it requires a
non-empty reason, writes a terminal voided successor (no result, probs preserved), and a
double resolution (score + void of one seal) is rejected at ledger aggregation with
"resolves exactly once". Server tests drive `GET /api/v1/calibration` over a real tmp
ledger built by the same functions.

## Calibration record ("After the whistle")

`golavo_core.calibration.calibration_summary(artifact_dir)` is a pure, deterministic,
self-validating function of the immutable ledger: chains sorted by kickoff, one
resolution per seal, counts that must reconcile (`sealed + abstained = scored + voided +
pending`), running log loss/Brier/mean-assigned-probability over scored chains, and
reliability bins computed by the same `_metrics` used by the backtest evaluator (one
definition of calibration, two surfaces). Served read-only at `GET /api/v1/calibration`
(recomputed per request; an empty ledger returns an honest zero-count record). The UI's
new **Ledger** view (`#/ledger`) renders counts, running calibration, the reliability
diagram, and every sealed→scored/voided pair with links into artifact details; voided
artifacts display their recorded reason. Backtests stay under **Evaluation** — the split
is explicit in copy and code. Sample fixtures regenerated at 0.2.0 with a conflict-free
supersedes graph; the UI's forecast/calibration mocks are now generated from those same
fixtures by `scripts/generate_sample_artifacts.py`, so mock ledger links always resolve.
Verified in-browser (mock and live-API modes): no console errors.

## Live demo (task 5) — honest status

At implementation time (2026-07-11T04:33Z–05:13Z UTC) the pinned snapshot (= upstream
HEAD `ddd7249`) carried three scheduled fixtures: Spain–Belgium 2026-07-10 and
Norway–England / Argentina–Switzerland 2026-07-11. All three day-proxy kickoffs
(00:00 UTC) had already passed, so **no genuinely sealable fixture existed** — sealing
one anyway would have been exactly the backdating this project forbids. The reproducible
test (above) carries the proof of the loop; the moment upstream publishes the next
round's scheduled fixtures, a live seal is one command:
`golavo seal --pack packs/martj42-internationals-<newref12> --date … --home-team … \
--away-team … --as-of <now>` followed by a commit+push before the day-proxy kickoff.
(Upstream was re-checked at 2026-07-11T05:20:46Z, immediately before this handoff was
committed: still `ddd7249`, no newer ref.)

## What shipped

1. Parameterized, retention-first snapshot builder + append-only registry +
   registry-aware provenance validation (CI).
2. Anchored forward-seal invariants (data-state anchor, day-proxy kickoff, leakage
   guard, scheduled-only targets).
3. Score-from-strictly-newer-snapshot confirmed and re-anchored; superseding scored
   artifacts never mutate seals.
4. Deterministic CI forward-loop + postpone/void tests over two real retained refs.
5. `void_forecast` wired into the loop with a mandatory recorded reason + `golavo void`
   CLI; scored artifacts cannot be voided, voids are terminal.
6. Real calibration record: core aggregator + `GET /api/v1/calibration` + Ledger UI,
   strictly separated from backtests.
7. Contract 0.2.0 (additive), UI contract mirror accepting 0.1.0/0.2.0.
8. Docs: README, prediction-ledger, coverage, packs README, CHANGELOG, this handoff.

## Known gaps (deliberate, stated)

- **Kickoff-time proxy:** the source has dates only; kickoff is 00:00 UTC on match day
  and seals close the day before. No precise kickoff times are faked; T-60m is unusable
  for internationals.
- **Internationals-only forward loop:** club sources are too stale for live sealing —
  explicit non-goal until a source with verified cadence is accepted.
- **The real ledger starts empty:** `data/artifacts/` contains no seals yet because no
  sealable fixture existed at ship time (see Live demo). The first genuine seal awaits
  the next upstream refresh; nothing synthetic will be committed there.
- **Upstream commit times are upstream-asserted;** publication (pre-kickoff commit/push)
  remains the real forwardness proof. Hash-chained cross-artifact ledger still planned
  (ADR-0001).
- **AI narration / BYOK / desktop:** still deferred per ADR-0001.
- **Retention grows the repo** (~3.7 MB per retained `core` snapshot); acceptable now,
  revisit if refresh cadence increases (e.g. move retained packs to Releases while
  keeping manifests in-tree).
