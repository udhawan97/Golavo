# Golavo domain language

The words below mean one thing in this codebase. They are the names the code
uses, so a search for a term finds the module that owns it.

## Sources and provenance

**Pack** — a directory under `packs/` holding pinned upstream bytes plus a
`manifest.json` declaring every file with its sha256. The manifest is the
provenance boundary: `validate_pack` hashes every declared file and rejects any
undeclared one, so an unhashed overlay can never influence an index.

**Snapshot** — an entry in a registry (`packs/snapshots.json` and its
enrichment/isolated siblings) naming a pack and the upstream ref it was pinned
at. Registries are append-only; refreshing a source adds an entry rather than
replacing one, so a retained snapshot stays valid evidence for every artifact
sealed against it.

**Snapshot anchor** — the instant a snapshot's data state verifiably existed:
the upstream commit time where known, else our retrieval time (strictly later,
so it never overstates availability). Decides which pack is current.

**Active pack** — the current pack for a source and, for a club source, a
competition: the greatest snapshot anchor in its group. Owned by
`golavo_core.packstore`; both the index build and the seal path resolve through
it so search and sealing can never disagree about which bytes are current.

**Generation** — one materialised output of a runtime refresh, activated by an
atomic pointer swap (ADR-0004). The active and previous generations are the
rollback boundary; the committed bundle is the final fallback.

**Match index** — the single frozen Parquet (`data/index/matches_index.parquet`)
over every CC0-cleared pack, plus its `matches_index.meta.json` sidecar. The
build is pure, so the same packs always produce byte-identical bytes.

## Identity

**Fold** — the diacritic-free, casefolded search key written into the index as
`home_norm`/`away_norm`. One implementation, in `golavo_core.identity`.
Idempotent, so an already-folded column and a raw upstream spelling agree.

**Fixture key** — `(day, home, away)`, optionally scoped by competition; how two
sources are shown to be talking about the same fixture. Result settlement grades
a seal only where two sources agree on one, so the fold and the key must be
shared, not merely alike.

**Canonical team** — the club-alias resolution (`TSV 1860 München` → `1860
München`) applied to a raw upstream spelling before it reaches the index. A
different operation from the fold, against league-scoped tables in the ingest
layer.

**Match id** — a within-source row id, `m_<sha256[:16]>` over that source's own
identity fields plus an occurrence number so a genuine repeat fixture does not
collapse. Each source keeps its own fields; only the minting mechanism is shared
(`golavo_core.ingest.matchframe`).

## Time and leak-safety

**Kickoff precision** — whether a row's `kickoff_utc` is a real instant
(`exact`, from a kickoff overlay) or the date's midnight (`day`). Upstream
clocks are venue-local, so calling one UTC would be a false instant.

**Order instant** — the sharpest instant a row can be ordered by: its exact
kickoff where one exists, else its date's midnight. Ordering by calendar date
treats every fixture on a day as simultaneous.

**Leak-safe cutoff** — one second before kickoff. The conservative boundary a
forecast may learn up to, deliberately not tightened further; the residual
day-precision exposure is disclosed rather than hidden.

**Training view** — everything one fixture may honestly learn from: rows before
the cutoff, scoped to the fixture's own source (and, for a club fixture, its own
competition), never its own row, with the no-future-rows guard already run.

**Completed view** — the read-path counterpart: completed matches at or before
an instant, for a board rather than a fit. Same ordering rule, no source
scoping, no self-exclusion.

## The forecast record

**Seal** — recording a forecast for a scheduled fixture before kickoff, as an
immutable artifact naming every snapshot it drew on. Never edited afterwards.

**Settlement** — grading a sealed forecast once a result exists, and only where
two independent sources agree on it. Disagreement fails closed.

**Retrospective** — replaying every match of a tournament at its own cutoff, and
proving the story's index and the seal's pack are one snapshot by comparing
digests rather than merely stamping them.

**Display-only** — a fact shown beside a forecast that may never enter model
inputs, training data, calibration, settlement or a sealed artifact. Match
context (ADR-0006), the weather forecast and the ODbL overlay (ADR-0005) are all
display-only.
