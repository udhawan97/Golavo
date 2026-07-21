---
title: Match Notes & optional enrichment
description: How Golavo turns deterministic match evidence into an editorial Match Notes read, and where optional lineup enrichment stops.
---

**Match Notes** supplies the descriptive evidence inside the cockpit's matchday programme. It
reorganizes facts that already cleared the engine's sample, freshness, and source guards; it
does not create new facts or become a second forecast model.

## What ships today

- a cover story chosen only after the fixed-rule **Three things to know** have been removed;
- each side's last-five pre-kickoff form timeline, with venue, opponent, deterministic streak,
  and a compact goal-difference trend;
- the goal model's attack and defence profile, explicitly labelled as fitted from results;
- guarded goal-timing bands and penalty-goal share when those notebook facts are present;
- scorer spotlights when the vendored source actually contains scorer data;
- a dedicated **Competition context** band, a like-for-like **Direct comparison**, and separate
  home/away team lanes for records that only one side qualifies for; every fact retains its
  sample, minimum sample, freshness, date range, scope, and source disclosure;
- coincidences preserved in a quarantined **For the pub** sidebar, capped and never shown to AI;
- a programme colophon naming the fixed fact family, rule-set version, as-of date,
  suppressed-candidate count, and sources.

Sparse data stays sparse. A section renders only when its typed evidence exists; Golavo does not
fill the page with inferred tactics, players, or formations.

The grouping is presentation-only and deterministic. Competition facts never sit under a team;
only matching templates share a comparison row; unmatched records stay in the lane of the team
they describe. If a counterpart was promoted into an earlier programme section, the lane links
there instead of claiming that the record does not exist.

## Typical formations: progressive enhancement

The UI includes a strict parser and mini-pitch renderer for conventional ten-outfield-player
formation strings. It renders only from a future typed enrichment response and always labels the
shape **typical, from recent lineups — not today's team sheet**.

The network adapter is intentionally **not enabled**. The planned source is API-Football
with a per-user key, off by default, a visible daily quota, and a permanent local cache for finished
lineups. Before that adapter ships, its free-season coverage and real quota headers must be verified
with a user-owned key. The core game, models, pick records, sealed artifacts, and AI numeric
whitelist never depend on it.

## Authority boundary

```text
vendored results -> deterministic analysis and facts -> Match Notes presentation
optional lineup API -> display-only enrichment ------^ (never model or pick input)
```

See [Fact & Coincidence engine](/Golavo/methodology/facts/) for the registered fact rules and
[Privacy & security](/Golavo/privacy-security/) for the local-first network boundary.
