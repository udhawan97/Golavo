# Golavo scheduled update plan

Prepared 2026-10-19, America/Chicago. Planning baseline:
`6af0273568f21414cc9849ec4be036aec759863f`.

The next scheduled runs should strengthen dependency and platform verification,
make season rollover failures easier to diagnose, and exercise recovery through
the real product. Independent club settlement follows a separate source decision.
Ship complete improvements in small increments; do not wait for this entire plan
to finish before evaluating a release.

This is the canonical forward implementation queue for this planning cycle.
[engineering-log.md](../../engineering-log.md) is the scheduler entry point and
holds the current phase and latest evidence. Historical handoff plans remain
design history; their old “not implemented” lists are not current work orders.
The [public roadmap](../../docs-site/src/content/docs/roadmap.md) retains the wider
product direction.

## Verified starting point

| Observation | Evidence and implication |
|---|---|
| Local `main` and the live remote main resolve to the baseline above | Git inspection on 2026-10-19; the worktree was clean before this documentation task. Another existing CAPO checkout is present and must be preserved. |
| Baseline CI and Pages workflows completed successfully | [CI run 39149433220](https://github.com/udhawan97/Golavo/actions/runs/39149433220), [Pages run 39149433172](https://github.com/udhawan97/Golavo/actions/runs/39149433172). These establish workflow results at that SHA, not today's native acceptance or a fresh dependency audit. |
| Latest release metadata reports v0.20.0 | [Release](https://github.com/udhawan97/Golavo/releases/tag/v0.20.0), published 2026-09-12. Asset and installed-app claims in [the release record](../releases/v0.20.0.md) are historical and must be rerun for the next candidate. |
| Fifteen dependency PRs were open and no issues were open | Live GitHub inventory on 2026-10-19. Requery before selecting work; an open update is not evidence of a vulnerability. |
| Desktop Rust tests run on macOS in normal CI; frozen sidecar smoke runs on macOS and Windows | [ci.yml](../../.github/workflows/ci.yml). Windows sidecar smoke does not execute the Windows Rust shell tests or installer/update/recovery journey. |
| Existing Playwright configuration runs Chromium against mock data | [playwright.config.ts](../../ui/playwright.config.ts). This does not establish live API, native Safari, WKWebView, or Windows WebView acceptance. |
| Forecast readiness, refresh receipts, generation diffs, dossiers, and archive recovery already exist | [fact sheet](../public-surface-fact-sheet.md), [ForecastReadiness.tsx](../../ui/src/components/ForecastReadiness.tsx), [refresh_jobs.py](../../server/golavo_server/refresh_jobs.py). Extend and verify these surfaces rather than creating replacements. |
| Domestic adapters already compute the European season and allowlist source paths | [refresh_sources.py](../../server/golavo_server/refresh_sources.py). Rollover needs boundary evidence and precise failure reporting, not another seasonal fetch engine. |
| Club seals deliberately remain pending without independent result agreement | [seal.py](../../server/golavo_server/seal.py), [settlement.py](../../server/golavo_server/settlement.py), public roadmap. Two repositories or URLs are not proof of two independent sources. |

The existing Graphify query supplied navigation, but its output was truncated and
the graph predates this planning baseline. The source files and current GitHub
state above are the authority for these statements. No new runtime, package,
provider, accessibility, or accuracy acceptance is claimed by this planning work.

## Scheduling and execution rules

The locally configured **WEEKLY CAPO — ENGINEERING AUDIT, PHASED PROGRESS, AND
VERIFIED RELEASES GitHub a** heartbeat is active for Sunday at noon; its prompt
specifies America/Chicago. The next nominal slot after this plan is October 25,
2026. It audits the account and selects at most two repositories for substantial
work, so Golavo is eligible for consideration, not guaranteed that slot.

No cadence, enabled state, model, notification policy, or saved automation prompt
is changed here. Daily Elf and Mobster are mentioned in CAPO's instructions, but
their runnable configurations were not established in this planning pass. All
runners should use the same repository queue when assigned Golavo.

1. **Resume before starting.** Read applicable instructions, this plan, the latest
   engineering-log entry, open PRs, CI, and worktrees. Refresh remote identity and
   candidate SHA. Reuse an existing matching PR. Never reset, clean, stash, delete,
   or take over unrelated work to simplify a run.
2. **Select one bounded slice.** Critical security, data-loss, and broken-build
   repairs take precedence. Otherwise use the phase order below. A run may finish
   less than one phase; it must not start a second substantial implementation slice.
   Set a time budget at run start and reserve its last quarter for validation,
   review, and handoff. Time pressure never waives a gate.
3. **Establish exclusive ownership before editing.** Verify exclusive repository/
   scope ownership through an existing shared coordinator or serialized runner.
   A checkout-local engineering-log entry is evidence, not a lock. If exclusivity
   cannot be established, defer overlapping work. Then record the run, branch/PR,
   base SHA, phase and slice, and touched surfaces in the log. A stale claim
   requires evidence the prior run ended before takeover. Preserve isolated
   worktrees and serialize integration with a fresh remote-head check.
4. **Verify the gap.** Reproduce the missing behavior or coverage before changing
   it. If already satisfied, record the exact evidence and close that slice without
   manufacturing a change. A baseline failure becomes a bounded repair; it is not
   silently attributed to a new feature.
5. **Apply the council gates below.** The present plan review does not certify a
   later implementation. Bind every implementation review to its final diff,
   contract versions, tests, and candidate SHA.
6. **Integrate only after required gates.** Follow current branch protections and
   repository policy; verify checks at the exact candidate and again after merge.
   Preserve a reviewable candidate when a required gate is unavailable.
7. **Leave a restartable handoff.** Record changed files, commit/PR, commands and
   results, failure signature, outstanding blocker, rollback, and one next action.
   Distinguish implemented, tested, merged, released, and deployed.

Use states `READY`, `IN_PROGRESS`, `BLOCKED`, `DONE`, and `DEFERRED`.
`DONE` requires the slice's acceptance evidence and integration status; research
completion must not be represented as feature completion. Never repeat an unchanged
failed approach. On the next run, a blocker without new evidence is retained while
an independent ready slice is selected.
Lettered steps can be intermediate checkpoints: for example, P1a and P1b do not
make a dependency family mergeable until P1c and candidate review are complete.

## Ordered phases

Effort estimates are planning ranges in focused scheduled sessions, not delivery
dates. A session's available time and external runners can change these ranges.

| Phase | Outcome | Initial state | Dependencies | Estimated effort |
|---|---|---|---|---|
| P1 | Resolve verified dependency risk and prevent lock drift | READY for triage | Fresh audit and existing PR checks | 1–3 sessions |
| P2 | Execute Windows shell tests and preserve cross-platform acceptance evidence | READY after P1 triage | Usable Windows CI runner; packaging acceptance needs an actual target environment | 1–2 source sessions plus native acceptance |
| P3 | Explain and safely recover from incomplete season rollover | READY for baseline verification | Existing approved adapters; no newly approved source required for synthetic tests | 2–3 sessions |
| P4 | Verify and repair refresh, analysis, and recovery user journeys | READY for baseline verification | P3 response changes, if any; independent startup cases may run earlier | 2–3 sessions |
| P5 | Decide whether independent club settlement can lawfully proceed | CONDITIONAL research | Fresh primary-source and independence evidence | 1 bounded research session; implementation estimate only after approval |
| P6 | Release a useful completed slice with exact-artifact acceptance | CONDITIONAL | At least one complete useful slice and every applicable release gate | 1 preparation session plus target acceptance |

P5 must never block P1–P4 or a qualified P6 candidate. P6 can run after any useful
completed slice; it is not a requirement to wait until the end of the table.

## Phase 1 Dependency maintenance with deterministic inputs

**User value:** reduce demonstrated dependency risk without silently changing
forecast bytes, packaging reproducibility, or the working UI.

**First run:** inventory and evaluate the existing PRs; select one compatible
dependency family with current evidence. Runtime/security findings take priority
over tooling cosmetics. If no actionable finding exists, preserve that result and
move to P2 instead of upgrading merely to create activity.

At the baseline, candidates include cryptography #130, pandas #117, Starlight #134,
paired React #110/#108, and build/test tooling #111/#112/#113/#126/#128/#129/
#131/#132/#135/#136. Numbers are discovery hints; read their current versions,
diffs, upstream release notes, and checks before reuse.

**Implementation slices**

- P1a: reproduce audit or compatibility evidence and select one family. Do not
  assume a major test-tool update is compatible or that separate React and
  React DOM updates may land independently.
- P1b: update that family and every affected source/release lock through the
  existing tooling. Use [packaging guidance](../../packaging/README.md) and the
  release workflow's pinned environment. Do not hand-edit hashes or replace
  immutable SBOMs/checksum files belonging to an already published release.
- P1c: verify clean install, source tests, and packaging inventory agreement;
  document only actual behavior changes. Preserve unaffected dependency families
  for later runs.

**Acceptance:** applicable fresh security audits pass policy; exact candidate CI
is green; affected source and release environments agree. A numeric/core dependency
change requires rebuilding the index into a disposable output and comparing it
with committed bytes and metadata. If bytes differ, investigate the cause and
regenerate through the repository's procedure; never approve unexplained drift.
Any model behavior change additionally requires chronological backtests and RPS/
log-loss comparison. New fixtures cannot manufacture improved accuracy.

**Verification owners:** `core/pyproject.toml`, `server/pyproject.toml`,
`packaging/`, UI/docs package locks, `scripts/release_inventory.py`,
`scripts/tests/test_contract_versions.py`, and `.github/workflows/ci.yml`.
Run the corresponding Python/UI/docs gates in the verification matrix below,
plus release inventory checks whenever packaged dependencies change.

**Rollback and stop:** revert the isolated source/lock commit and regenerate
derived files with the prior environment if needed. Stop on unreviewed license
changes, unexplained numerical drift, incompatible APIs, or an unresolved audit
finding. Do not loosen audit levels or remove tests to land an upgrade.

## Phase 2 Windows shell coverage and recovery evidence

**User value:** catch Windows-specific updater and shell failures before users
receive an installer.

**First slice P2a:** extend the existing `desktop-check` job to run locked Rust
tests on macOS and Windows, both with default features and with `--features updater`.
`desktop/src-tauri/Cargo.toml` has an empty default feature set; default tests do
not compile the signed-updater engine. Record feature flags with every result.
No production signing credential is needed simply to compile/test that feature;
use controlled fixtures for signature rejection.

Preserve the UI build prerequisite and host-triple placeholder sidecar convention.
Use an explicit shell or platform-specific command; append `.exe` to the Windows
placeholder filename. Clearly identify this as shell test coverage; placeholders
cannot establish frozen-sidecar or installed-app success. Retain the existing real
macOS/Windows sidecar smoke jobs.

**Second slice P2b:** run the existing updater/recovery tests on the Windows target;
add a focused regression test only for a demonstrated uncovered branch or defect.
Inspect `desktop/src-tauri/src/updater.rs`, `fallback_update.rs`, and `lib.rs`.
Cover applicable path handling, executable selection, interrupted replacement,
retained recovery journal, invalid signature, missing artifact, and restart failure
using disposable files. Reuse current fixtures instead of building a second updater.

**Acceptance:** normal PR CI compiles and executes Windows-target Rust tests,
including applicable `cfg(windows)` cases and enabled-updater paths; default and
updater-feature macOS lanes remain green; both real frozen sidecars pass smoke.
Persist job URLs, OS/architecture, feature flags, exact SHA, and actual
coverage. Separately exercise installed upgrade/restart/rollback on disposable
macOS and Windows profiles before any release claiming those paths.

**Stop and rollback:** a missing Windows environment blocks native acceptance,
not an excuse to call a cross-compile an install test. Never disable required jobs
because the matrix reveals a failure. Revert the isolated workflow change if it
is itself defective; keep the uncovered product failure as an explicit blocker.
New signing credentials, trust identities, and OS notarization remain outside
this phase.

## Phase 3 Season rollover readiness and last known good data

**User value:** when a new season is absent or incomplete, the app explains which
verified data is usable, which capabilities remain withheld, and what to do next.

**Baseline:** seasonal selection already exists in `current_european_season()`.
Refresh state, activation receipts, and forecast readiness already exist.
Establish which rollover cases are missing before editing. The product increment
is a precise reason and safe retry through these surfaces, not another dashboard.

Preserve the existing distinction between valid partial data and invalid data.
`build_domestic_runtime_pack()` can return a verified pack with `capability=partial`;
the coordinator can also retain one absent competition while updating other sources.
This phase does not change that activation policy:

| Candidate state | Rows and pointer behavior | Capability and simulation |
|---|---|---|
| One competition absent upstream | Retain that competition's active verified rows. A verified generation containing updates from other sources may still activate. | Disclose last-known-good data and its actual season; do not claim the missing season is available. |
| Valid partial schedule | Existing policy may incorporate its verified rows and activate the generation after all safety/manifest checks. Preserve history through the current merge rules. | Explicitly partial; withhold full-season simulation until its completeness/result-gap certificate passes. Partial never means invalid or complete. |
| Invalid bytes, identities, provenance, or failed candidate safety check | Reject the candidate transaction and keep the previous active pointer and bytes. | Show the actual rejection reason. Do not silently accept other pieces of a rejected transaction. |
| Valid complete schedule | Activate only after all existing generation, safety, manifest, and receipt requirements pass. | Enable only capabilities certified by the actual data and current rules. |

Test these outcomes at both competition and whole-generation level. Reuse existing
job/activation locks. Any proposal to reject all partial next-season activation
would be a separate policy change requiring its own design and council review.

**Implementation slices**

- P3a: exercise a synthetic June 30 to July 1 boundary, missing upstream path,
  partial schedule, promoted/relegated team identities, duplicate fixtures,
  ambiguous day-only kickoffs, malformed results, and a complete valid schedule.
  Trace `refresh_sources.py` → `refresh.py` → `refresh_jobs.py` →
  `refresh_state.py` and the complete-season certificate in
  `core/golavo_core/season_outlook.py`.
- P3b: if existing errors conflate missing/partial/invalid data, carry bounded
  machine-readable reasons through the existing refresh contract and Settings
  surface. Show active season/generation, last verified time, attempted season,
  failure reason, and a permitted retry path only when those values are verified.
  Do not derive coverage from a successful HTTP status or infer kickoff instants.
- P3c: verify atomic activation and rollback: invalid candidates do not move the
  pointer; valid candidates create the appropriate receipt; analysis and seals
  resolve the same verified generation. Preserve older immutable artifacts.

**Acceptance:** deterministic fixtures prove all boundary cases and rollback.
The active generation's identity and bytes are unchanged after a rejected transaction;
an absent competition alone does not necessarily reject the whole generation.
No partial schedule is labelled complete or fed to full-season simulation.
The Settings/readiness flow conveys missing versus rejected versus usable data,
without implying that freshness is confidence. Repeated explicit refresh is safe,
and cancellation/navigation cannot show a late result under a different identity.

**Tests and contract work:** extend `server/tests/test_domestic_refresh.py`,
`test_refresh_sources.py`, `test_refresh_state.py`, `test_refresh_integration.py`,
`test_refresh_production.py`, `test_season_outlook_api.py`, and relevant UI tests.
Change only contracts actually needed; synchronize JSON Schema, Python ownership,
TypeScript types, mocks, and version/drift checks together.

**Rollback and stop:** default to the verified prior generation or bundled fallback;
revert the feature commit without deleting retained packs or user state. Use
synthetic fixtures for future seasons. Real future-season rows require verified
publication, rights, exact paths, identities, and the existing activation checks.
Do not claim a complete 2027–28 or another season, or enable full-season simulation,
until its completeness certificate passes. A missing schedule is a valid deferred
outcome; valid partial rows retain the existing policy above.

## Phase 4 Recoverable user journeys and accessible failure states

**User value:** users can understand and recover when the local engine, refresh,
analysis, or archive operation fails.

**Scope:** begin with the current startup, Settings, Forecast Readiness, Match
Cockpit, and Trust Center. Keep their existing information architecture. Every
product fix must start with a reproducible defect or missing acceptance case.
No speculative redesign or generic framework migration belongs in this phase.

**Implementation slices**

- P4a: exercise engine unavailable → retry → ready, and ready → engine disconnect.
  Verify timeout messaging, keyboard reachability, focus after retry, and preserved
  route intent. Owners: `ui/src/lib/startup.ts`, `StartupSplash.tsx`,
  `EngineWarmup.tsx`, and corresponding tests.
- P4b: exercise refresh preview/status → successful activation or rejected update →
  match analysis. Deliberately navigate to another match during a slow request.
  Verify exact identity, cancellation, retained prior data, visible error and retry,
  and no stale response masquerading as the newly selected match.
- P4c: exercise a disposable archive's inspect → recovery drill → explicit restore
  and an invalid archive's rejection. Verify consent boundaries, existing-ledger
  preservation on failure, focus/announcements, and the exclusions documented in
  the fact sheet. Never use the owner's actual ledger for destructive tests.

**Acceptance:** selected journey tests execute against both relevant mocks and a
real local sidecar with synthetic/disposable data. Existing unit coverage remains
useful, but rendered static HTML alone does not prove effects, state, or interaction.
Add meaningful client-render or end-to-end checks for demonstrated gaps.
Use keyboard-only navigation, reduced motion, and narrow/wide layouts; retain
the repository's serious/critical accessibility-violation threshold.

Run final browser acceptance in native Safari for browser-visible changes and in
the installed Tauri app for shell/OS behavior. Use Safari Browser Use first for
interactive browser work. Chromium and Playwright WebKit results must retain their
actual labels. VoiceOver acceptance requires a real VoiceOver run; axe is not a
substitute. Record failed and unavailable target checks explicitly.
Safari may verify read flows and rejection boundaries. P4c archive restore and
checkpoint mutations require an authorized disposable desktop session with its
private launch token. Never weaken desktop authorization or expose a token to
make a browser test pass; a real-sidecar browser run cannot prove desktop restore.

**Rollback and stop:** each journey is an independent commit with no data migration
by default. Revert its UI/controller changes if necessary. Stop on unclear user-data
ownership, unapproved provider/model download, or unavailable required native
acceptance; do not remove failure handling or consent to make a demo pass.

## Phase 5 Independent club settlement source decision

**User value:** establish whether recorded club forecasts can eventually settle
automatically without weakening the two-source rule.

**First and only initially ready slice P5a:** investigate at most two plausible
sources using current primary documentation. Produce one dated decision record
with source origin, independence from OpenFootball's underlying results, permitted
storage/redistribution/settlement uses, coverage, historical revisions, result
finality, rate limits, cost, and point-in-time retrieval semantics.

No specific candidate is preapproved by this plan. Historical source research is
a lead to recheck, not present legal permission. License ambiguity, shared upstream
lineage, incomplete fixture identity, or prohibited settlement use means `DEFERRED`.
Keep club seals pending. A decision to reject both sources completes the research
slice and prevents wasted implementation.

**Conditional later slices:** only after the source decision and a fresh council
design review approve a concrete adapter may a scheduled run implement it under
its existing authority. Use a narrow typed result-observation contract, exact
competition/season/team/fixture mapping, recorded provenance and result finality,
and fail-closed agreement. Mirrored repositories do not count twice. Postponed,
abandoned, replayed, corrected, disputed, and same-team/same-day fixtures must not
be settled by fuzzy joins. Scoring appends a successor without modifying a seal.

**Acceptance for any later implementation:** synthetic agreement/disagreement,
duplicate lineage, missing identity, finality, and upstream correction tests;
re-running settlement is idempotent; disagreeing sources remain pending with a
reason; retained source evidence is permitted and reproducible. Run provenance,
license, correction, and research isolation checks plus scoring/artifact tests.
Existing ODbL and proprietary adapters remain excluded wherever current contracts
exclude them; this plan grants no exception.

**Stop and rollback:** no purchases, credential creation, new provider consent,
redistribution, or policy exception is implied. Seek an owner decision only if a
specific reviewed proposal requires one. Disable/revert a new adapter without
rewriting seals or previously recorded lineage. Any correction to an already
scored successor needs the existing append-only correction policy or a separately
reviewed design; never silently rescore history.

## Phase 6 Candidate verification and justified release

**User value:** deliver a useful verified improvement without overstating its
platform coverage or data capabilities.

Use the existing release process and current scheduler authority. This planning
task does not create a tag, release, or new deployment. Select the next version
from the actual completed changes and the repository convention at execution time.

**P6a prerequisite:** establish an executable hold between candidate packaging and
stable publication. The current release workflow builds on a version tag and
immediately undrafts after asset upload; its draft step is not a native-acceptance
review window. A manual build accepted locally followed by a tag rebuild does not
prove the published bytes were accepted.

Make a separately reviewed, bounded change to the existing release workflow that
retains candidate artifacts, records target acceptance against each artifact
digest, and permits publication only of those same accepted bytes. Bind the
acceptance record to source SHA, workflow run/artifact identity, target, feature
flags, digests, executed checks, and evidence locations. Missing records, mismatched
digests, changed source, expired artifacts, and any rebuild must hold publication
and require renewed applicable acceptance. A caller-supplied `passed=true` is not
acceptance evidence. Do not bypass protections or create new signing identities
or security-sensitive permissions to implement this gate. If the existing
authorized infrastructure cannot support it, record the concrete owner decision
and hold publication.

Test this workflow change without publishing: a missing/altered acceptance record
or rebuilt payload cannot reach undraft; the accepted payload's digest survives
promotion unchanged. Do not create a release tag through the old automatic path
while this prerequisite is unresolved.

**P6b candidate and publication**

1. Select a complete independent slice, supported targets, limitations, rollback,
   and delta from the latest release. Prepare version changes, README, relevant
   public docs, changelog, release notes, download/version references, and fact
   sheet without claiming publication. Update screenshots only where warranted.
   Refresh the existing Graphify graph with the incremental flow and confirm one
   scoped query against source. A stale-graph update failure blocks publication.
   Then freeze the final source SHA.
2. Run full source/contract/data checks, exact release-environment locks, and
   SBOM/inventory validation. Build and retain candidate packages through P6a.
3. For every packaged candidate exercise clean install/first launch, existing-
   version upgrade, app/sidecar startup, offline operation, exact-identity match
   analysis, and update recovery on supported targets. Also verify local-model
   readiness/cancellation, Fast/Deep analysis on a real fixture, deterministic
   verdict wording, and visible error states using already authorized local
   resources. Missing required resources hold acceptance; do not download a model
   or infer provider consent. Provider fixtures cannot prove live entitlement or
   delivery. Record acceptance against the exact package digests.
4. Complete candidate council review over the frozen source, package digests,
   evidence, and proposed claims. Any subsequent source/version/docs/generated
   change requires a new freeze and affected checks/builds/acceptance/review.
5. With every required gate satisfied, promote the accepted bytes through P6a.
   Verify tag/source alignment, every expected platform asset, signatures where
   configured, `latest.json`, `SHA256SUMS.txt`, inventories, real download paths,
   and the live Pages surface. Keep source merge, release, and website outcomes
   separate in the handoff. Publication confirmation in a later documentation
   commit is recorded as post-release evidence, not as the packaged source SHA.

**Hold conditions:** no enforceable exact-artifact publication gate, absent signing material required by current policy, missing
native acceptance, failed security check, inventory mismatch, broken recovery,
stale graph, or source/candidate drift. Preserve the candidate and exact blocker;
never change gates to obtain a release. OS signing/notarization remains an explicit
separate capability until credentials and actual validation exist.

**Rollback:** before publication, keep the prior release current. After
publication, use the established signed recovery/forward-fix procedure; never
replace immutable published assets with different bytes under the same identity.

## Verification matrix

Resolve commands from current repository guidance before running. Do not claim a
command passed because it appears here. Use isolated environments and disposable
data for tests that write artifacts.

| Changed surface | Required evidence |
|---|---|
| Python/API behavior | Focused regression first; `make test`, `make lint`; relevant contract/drift checks and `make validate` for provenance/data/isolation changes |
| Model, source pack, index, settlement | Above plus deterministic rebuild, relevant leakage/agreement tests, provenance/artifact validation; model changes require chronological evaluation and RPS/log-loss comparison |
| UI interaction | `cd ui && npm test && npm run build && npm run test:e2e`; lint through `make lint`; real sidecar journey and native target acceptance where relevant |
| Desktop or updater | Build UI prerequisite; `cargo test --manifest-path desktop/src-tauri/Cargo.toml --locked` and the same command with `--features updater` on supported targets; frozen-sidecar smoke; disposable installed-app acceptance for changed native paths |
| Documentation | Check local links and `git diff --check`; `cd docs-site && npm run check && npm run build` for public-site changes |
| Release candidate | All applicable above plus repository release preflight, lock/SBOM/inventory checks, native installation/update/recovery, Graphify update/query, publication and public-surface verification |

For every result record command, exit status, tested SHA or build digest, relevant
environment, and a durable log/job location. Capture no credentials, proprietary
provider payloads, or private user data in committed evidence.

## Council review protocol for scheduled runs

Use the installed `council-review` skill. Four independent reviewers cover
evidence, coverage, risk, and outcome. Run exactly two full rounds, with four
actual verdicts per round; schedule reviewers sequentially when capacity is
limited. A reviewer must not recursively convene another council.

Before a material implementation slice, provide the reviewers with its current
gap reproduction, proposed change, contract/data boundaries, tests, rollback,
dependencies, and stop criteria. Round 1 challenges the plan. Reconcile valid
corrections against evidence; Round 2 confirms the revised plan. Each reviewer
must examine every phase in this plan during the present planning review.

After implementation, use the same two-round process for the final candidate
diff, test evidence, handoff, and proposed completion claims. Plan approval does
not replace implementation review, CI, source rights, native tests, or release
authority. Material edits after review require targeted acceptance from the
reviewer responsible for the affected blocker. A changed candidate invalidates
tests/review where that change affects their scope.

Proceed only with no valid unresolved blocker. Missing reviewers or required
evidence means a blocked gate, not simulated consensus. Keep reviewer transcripts
private; publish only decisions, material corrections, and evidence limits.

## Handoff record for the next run

Keep this concise record in `engineering-log.md`; do not create competing phase
trackers in issues or automation prompts.

```text
Run date and runner:
Phase / slice / state:
Base SHA / candidate SHA / branch / PR:
Current limitation and reproduction:
Change and user-visible outcome:
Checks: command -> result -> log/job -> tested SHA/environment
Council: plan rounds / candidate rounds / blockers / reviewed digest
Integration: pending or merged SHA and post-merge checks
Release / Pages: separate actual state, or not attempted
Rollback:
Failure signature, prior attempt, new evidence:
Next action and prerequisites:
```

## Deferred product directions

Persistent player form, manager dossiers, modelled xG/cards/corners/scorers,
transaction-level transfer payments, community packs, external checkpoint
anchoring, closed-app monitoring, and OS signing remain separate design/source/
credential decisions. None is justified merely by an attractive UI or an AI
explanation. Revisit only with the public roadmap's entry evidence. Broad router
refactoring and new infrastructure are also out of this queue unless a selected
slice demonstrates they are necessary.
