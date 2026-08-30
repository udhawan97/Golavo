# Match Study Desk and Transfer Desk — v0.19.0 plan

**Status:** implementation plan after Council Round 1
**Release shape:** bounded milestone, not completion of every requested forecast target
**Comparison point:** `v0.18.0..f3eb951` plus this implementation

## Product boundary

Golavo will become materially more useful for studying a match without becoming a
bet-placement or recommendation product. Deterministic and statistical models remain the
only owners of forecast numbers. AI may explain an accepted evidence bundle; it may not
verify, average, alter, or replace a model output.

The release must not add expected value, model-versus-bookmaker deltas, rankings, staking,
units, locks, affiliate links, bookmaker links, “value,” “best bet,” or recommendation
language. Where the interface shows `1 / probability`, it is labelled a **model-implied
mathematical equivalent**: no margin, no market movement, no recommendation.

Cards, corners, and player-scorer forecasts remain unavailable in v0.19.0. They need a
separately licensed point-in-time event corpus, deterministic target-specific models,
leakage controls, time-split evaluation, calibration, abstention, and numeric-whitelist
coverage. Sportmonks remains contractually excluded from model fitting, scoring,
settlement, calibration, AI evidence, and exports. The same boundary prevents card,
corner, or scorer bonus scoring in this release.

## Evidence and inspiration

The provider and open-source review is recorded in
[`docs/research/live-match-transfer-intelligence-expansion-2026-08.md`](../research/live-match-transfer-intelligence-expansion-2026-08.md).
It records official provider terms and endpoint contracts plus exact inspected commits and
licenses for OpenLigaDB Samples, Kloppy, socceraction, and floodlight. Golavo borrows only
the architectural lessons—provider adapters, typed capabilities, explicit missingness,
synthetic fixtures—not source code, assets, or upstream data rights.

## Delivery slice

### 1. Match Study Desk

Add an always-visible study surface inside the Match Cockpit, separate from the long-form
programme chapters. It presents a fixed, non-ranked set of mathematically distinct lenses:

- each deterministic model voice’s W/D/L distribution and modal call, never averaged;
- the council disagreement status and percentage-point spread, not a probability;
- the goal voice’s most-likely exact score and its probability;
- over/under 2.5 from the full joint score matrix;
- both-teams-to-score yes/no from the full joint score matrix;
- home and away clean-sheet probabilities; and
- information cutoff, model family, source, and history-support meaning.

Cards, corners, and scorer forecasts appear in a capability rail as unavailable with the
exact model/data-rights reason. The UI must never substitute provider predictions or AI
prose for these missing targets.

Acceptance tests cover non-averaged voices, mathematical metric types, unavailable target
states, prohibited recommendation language, invalid/zero mathematical equivalents,
keyboard focus, mobile layout, and reduced motion.

### 2. Foreground player context

Keep Sportmonks player data opt-in, BYOK, selected-match-only, foreground-click-only,
in-memory, and no-store. Upcoming and in-progress matches preserve predicted, confirmed,
or unverified lineup state. Completed matches use explicit **Fetch final player stats** and
**Refresh final player stats** wording. Every state shows fetch time and treats missing as
unavailable, never zero.

Current multi-match player form is not shipped: the approved connector has no retained,
point-in-time form series and the standard terms have not cleared a model corpus. The UI
and docs name that limit instead of calling one match “form.” No polling continues after
navigation, disable, disconnect, or app close.

### 3. Transfer Desk

Add a dedicated `#/transfers` page and a `transfer_desk` Sportmonks capability. The user
selects one top-five club from exact local current-season fixture identities. One explicit
fetch action may perform bounded HTTP pagination:

- exact Sportmonks fixture and distinct provider-team identity first;
- allowlisted team-transfer endpoint only;
- descending provider transfer date;
- at most four pages of 50 rows;
- current window defined as provider transfer dates in the preceding 365 days;
- a visible `partial` state if the page bound is exhausted before the window is complete.

Each result preserves transfer, player, type, from-team, and to-team IDs; date; completion
state; player/team/type names from included provider entities; and the nullable provider
amount string. The label is **provider-reported amount — currency unspecified**. Null stays
unavailable. Currency, installments, add-ons, sell-ons, agent/intermediary fees, training
rewards, and conditional consideration are visibly not reported, never zero. Rumours,
logos, photos, totals, currency inference, fee arithmetic, and payment-story generation are
out of scope.

The response carries fetch time, requested window, pagination coverage, terms version,
raw-response hashes, `raw_response_storage: not_persisted`, and explicit false permissions
for model, AI, scoring, settlement, calibration, and export use. Tests cover null/ambiguous
amounts, malformed or duplicate IDs, mismatched team identities, mixed arrivals and
departures, response limits, pagination truncation, cancellation, `401/403/429/5xx`, and
no-cache headers.

## Visual direction

The current Golavo system remains intact. The new signature is a compact **instrument
rail**: quiet graphite/navy surfaces, existing gold for model-owned values, steel for
metadata, green only for verified availability, tabular numerics, and tight alignment.
There is no trading-terminal cosplay, neon grid, or decorative chart junk. Mobile turns
the rail into labelled cards without hiding provenance. Motion is limited to one staged
reveal and is removed under `prefers-reduced-motion`.

## Documentation and release

Update the research record, this plan, README, docs-site navigation and relevant pages,
public fact sheet, changelog, v0.19.0 release notes, version metadata, and rendered
screenshots. Release prose calls this a bounded milestone and never claims current live
provider behavior unless an authorized credentialed smoke test actually succeeds.

Before tagging:

1. Preserve and hash `data/artifacts/follows/follows.sqlite3`; use temporary runtime paths
   for writer-capable tests; stage neither `data/artifacts/` nor provider data.
2. Audit every commit in `v0.18.0..HEAD` and derive release notes from the verified diff.
3. Run focused provider/UI tests, `make test`, `make validate`, `make lint`, UI unit,
   typecheck, build and Playwright gates, docs check/build, Cargo locked check, license and
   provenance gates, and `git diff --check`.
4. Render and inspect the Match Study Desk, Transfer Desk, Settings capability, completed
   Player Lens, mobile states, and public docs screenshots.
5. Run `graphify update .` and a scoped query on the merged release SHA.
6. Run Council Round 2 against the implementation and proposed completion report; close
   every valid blocker.
7. Commit with sign-off on the feature branch, merge into `main`, push `main`, verify CI,
   CodeQL, and Pages, bump/tag exact `v0.19.0`, and wait for the stable release workflow.
8. Verify tag/main SHA alignment, draft/prerelease state, every macOS/Windows installer,
   updater signatures, `latest.json`, `SHA256SUMS.txt` and signature, public release notes,
   and live documentation before claiming publication.

## Deferred gates

- deterministic card, corner, and scorer forecasts;
- bonus scoring for those targets;
- retained or background live-player/form history;
- a complete transfer payment breakdown from primary club/issuer disclosures; and
- any recommendation, bet placement, staking, or affiliate workflow.

These are deferred because the required data rights, evidence, or product authorization do
not exist—not because the interface lacks room for them.
