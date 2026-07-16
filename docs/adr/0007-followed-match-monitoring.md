# ADR 0007: Local-first followed-match monitoring

**Status:** Accepted  
**Date:** 2026-07-15

## Context

Golavo can refresh approved CC0 sources after a visible, consent-aware UI call,
but it has no account, push service, background helper, Login Item or
LaunchAgent. Users need a way to concentrate that existing refresh capacity on
selected fixtures without weakening source provenance, deterministic forecasts
or immutable seals.

The approved sources publish repository or season files, not per-fixture live
endpoints. A followed match can therefore narrow source revision checks and
post-activation reconciliation, but it cannot turn those sources into a live
score feed.

## Decision

1. Following is a local subscription stored under the writable forecast ledger.
   It never enables network refresh or notification permission by itself.
2. Automatic checks reuse the existing `off`, `check_only` and `auto_refresh`
   consent policy. They run on launch and when due while Golavo is running. A
   resume/focus check catches up after a suspended window. Closing Golavo stops
   checks.
3. No helper, daemon, tray process, Login Item or LaunchAgent is installed.
   Closed-app monitoring is a separate future product decision.
4. `scope=followed` selects the distinct approved CC0 sources represented by
   active follows. If an activated refresh is needed, the complete Phase 1
   source generation is still downloaded, validated and swapped atomically.
5. The v1 namespace is `core-cc0`. OpenLigaDB overlay identities and bytes are
   rejected. Geographic context remains display-only and offline.
6. A local `follow_id` is stable. Identity is repointed only by the same
   `match_id` or an exact upstream fixture key that its source adapter declares
   stable. Team similarity, date proximity and fuzzy aliases never merge
   identities automatically.
7. Changes are append-only events with field provenance and semantic
   deduplication. Unfollow is soft; explicit removal is a separate destructive
   action.
8. Following never modifies, backdates, replaces or settles a sealed forecast.
   Conflicting or unverified results cannot produce settlement availability.
9. Optional desktop notifications require an explicit Settings action and OS
   permission. They are generic, best-effort submissions for changes detected
   while Golavo is running. The durable in-app event remains authoritative.

## User-facing lifecycle contract

> Golavo checks followed matches on launch and periodically only while the app
> is running. Closing Golavo stops checks. No helper, Login Item, or LaunchAgent
> is installed.

> Notifications are sent only for changes Golavo detects while it is open. They
> do not monitor matches after you quit.

## Consequences

- The workflow remains free, keyless, local-first and network-free in policy-off
  mode.
- Source-file granularity means a followed refresh is not a live per-match
  request. UI copy must say “check approved sources,” never “live monitoring.”
- Some reschedules cannot be reconciled automatically. They remain visible as
  `identity_unresolved` until an exact source identity is available.
- A source report that conflicts with a sealed fixture is recorded as a
  quarantined observation; the active fixture and seal remain unchanged.

## Forbidden claims

Do not claim real-time, instant, background-after-quit, guaranteed notification
delivery, automatic settlement or current club coverage without a verified
source capability. Do not use betting, odds or urgency language.
