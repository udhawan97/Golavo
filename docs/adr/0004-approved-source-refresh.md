# ADR-0004: consent-first approved-source refresh

Status: accepted for implementation, 2026-07-15.

Golavo may check and refresh only `martj42/international_results`,
`openfootball/worldcup.json`, and genuinely published current-season files from
`openfootball/football.json`. The UI owns scheduling and must read an explicit
`off`, `check_only`, or `auto_refresh` preference first. Existing boolean consent
migrates to `check_only`. The sidecar does not self-schedule and no helper,
daemon, LaunchAgent, or closed-app refresh is included.

Every download is resolved to a full commit SHA, captured under immutable raw
receipts, parsed and validated before a complete candidate index is built. A
verified generation is activated by an atomic pointer swap. Active and previous
generations form the rollback boundary; bundled data remains the final fallback.
Refresh activation is all-or-nothing across the approved set. The pinned Git
tree is retained as the evidence for club capability, including honest absence.
Cross-source disagreements, completed-score rewrites, completed-match deletion,
and any removal or identity/kickoff mutation of a sealed fixture fail closed
without changing active data.

The deterministic engine remains authoritative. World Cup data may supply exact
fixture, kickoff, and venue fields but is not training evidence. Club capability
is `absent`, `partial`, or `complete` per current-season file and schedule
certificate; Golavo never infers publication or completeness.
