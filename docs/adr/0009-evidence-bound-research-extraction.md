# ADR-0009: evidence-bound match research and candidate extraction

Status: accepted for Phase 7 implementation

## Decision

Golavo's optional match research is a separate, foreground-only workspace. It
does not run when AI narration starts, does not crawl the general web, and does
not write authoritative match data. The user enables research, reviews a
preflight naming every destination, selects candidate URLs, and explicitly
starts each acquisition run.

DuckDuckGo HTML search is removed. Built-in discovery is limited to documented
Wikimedia APIs. A user-owned SearXNG endpoint may discover URLs, but its snippets
are never evidence and are never sent to AI. Federation or competition pages
require an exact registry policy and source-specific parser before use.

Every extracted value names one immutable capture with canonical URL, retrieval
time, license namespace, raw and canonical-text SHA-256, exact quote, and parser
or local-model version. Deterministic parsers run first. Local AI may fall back
only for alias and venue text in v1 and must return an empty candidate list when
the source does not state a value.

## Authority and correction boundary

Research candidates are untrusted. They do not enter evidence bundles, numeric
whitelists, match indexes, source packs, forecasts, seals, settlement,
calibration, model training, or exports. An explicit user action may copy a
reviewed candidate and bounded evidence excerpt into Phase 6 as a draft. The
correction service still performs no network fetch and all Phase 6 validation,
identity, license and conflict gates remain in force.

Wikipedia text is retained under a separate, non-exportable
`research-cc-by-sa-4.0` namespace. Wikidata structured data uses the existing
`enrichment-cc0` namespace. No source bytes are bundled.

## Operational limits

Research is off by default, performs no idle or closed-app work, uses serial
requests, and fails closed on unsafe addresses, redirects, content types,
oversized responses, hostile markup, cancellation or timeouts. A failed run
leaves the deterministic match experience fully available.
