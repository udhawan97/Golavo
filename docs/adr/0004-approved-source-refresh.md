# ADR-0004: consent-first approved-source refresh

Status: accepted for implementation, 2026-07-15.

Golavo may check and refresh only `martj42/international_results`,
`openfootball/worldcup.json`, `openfootball/football.json`, and one exact
current-season Football.TXT path in each of `openfootball/england`, `deutschland`,
`espana`, `italy`, and `europe` (Ligue 1). The eight repository identities and their
allowed paths are fixed in the registry; arbitrary repository or file selection is
not a refresh capability. The UI owns scheduling and must read an explicit
`off`, `check_only`, or `auto_refresh` preference first. Existing boolean consent
migrates to `check_only`. The sidecar does not self-schedule and no helper,
daemon, LaunchAgent, or closed-app refresh is included.

Every download is resolved to a full commit SHA, captured under immutable raw
receipts, parsed and validated before a complete candidate index is built. A
verified generation is activated by an atomic pointer swap. Active and previous
generations form the rollback boundary; bundled data remains the final fallback.
Refresh activation is all-or-nothing across the approved set. Domestic generations
retain the verified historical JSON pack and replace only the declared current-season
table with the country repository's pinned file. The pinned Git tree is retained as
the evidence for club capability, including honest absence.
Cross-source disagreements, completed-score rewrites, completed-match deletion,
and any removal or identity/kickoff mutation of a sealed fixture fail closed
without changing active data.

The deterministic engine remains authoritative. World Cup data may supply exact
fixture, kickoff, and venue fields but is not training evidence. A country repository
may supply current-season fixture identity, day-precision kickoff, completed results,
and training rows with field-level provenance; it is still only one result source, so
club settlement requires independent agreement. Club capability is `absent`, `partial`,
or `complete` per current-season file and schedule certificate; Golavo never infers
publication or completeness.
