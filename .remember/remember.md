# Handoff — 2026-07-16, v0.15.0 architecture release

## Where things stand

**v0.15.0 is on origin/main (c2a355b) and tagged `v0.15.0`.** Architecture-only release: five
deepenings from an `/improve-codebase-architecture` review, implemented TDD, verified,
documented, merged, pushed, tagged. All 7 CI jobs were green on c2a355b before the tag; the
tag fired `release.yml`, which builds and publishes the installers.

**Check on next session:** that the Release run finished and published DMG/MSI/EXE +
SHA256SUMS — `gh run list --limit 5`. Builds are unsigned pre-alpha, as before.

## What changed (each = one rule that had several homes)

1. `golavo_core.ingest.leak_safe_training_view()` — the kickoff-1s cutoff, source scoping,
   self-row exclusion and the no-future-rows guard are now inseparable. Was derived in four
   places; the scoping half existed verbatim twice. `server/golavo_server/analysis.py` no
   longer scopes at all.
2. `matches.SnapshotReader` — the retry/key/publish-gate/stamp/LRU dance, self-registering.
   Killed the hardcoded module-name tuple in `_reset_derivative_caches`.
3. `jobs.Lane` — per-lane stage vocabulary + id space. `Job.stage` default is now `"queued"`.
4. `retrospective.PackSnapshot` + `build(resolve_pack=...)` — agreement testable on plain data.
5. Server projects the trust fold onto `RETROSPECTIVE_FAMILIES`, emits required
   `omitted_families`; the React view stopped re-deriving the rule.

Plus: `capabilities.py` deleted (pass-through), two *wrong* claims fixed on the public
architecture page.

## Evidence

808 Python + 177 UI tests green; ruff + tsc clean; all 6 validators pass; docs site builds.
Sample artifacts byte-identical. **A/B'd the old sidecar (main, v0.14.2, port 8978) against
the new one (port 8977)** — every touched endpoint byte-identical except the version string
and analytics' now-minute-resolved `as_of_utc`. Live-proved the lane fix: v0.14.2's
retrospective cancel door returns `cancelled:true` for an AI-lane id; v0.15.0 returns 400.

## Deliberately not done

Merging the retrospective's poll loop into `usePolledProgress` — that hook hardcodes the
`/ai/jobs/` route and AI stage union and surfaces no result payload. Sharing it would mean
flags for two shapes.

Full detail in memory: `architecture-deepening-v0-15-0.md`.
