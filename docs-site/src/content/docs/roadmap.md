---
title: Roadmap
description: The smallest trustworthy product first, with entry/exit criteria and kill switches — then the full aspirational Golavo.
---

Golavo is built data-first. The first phase was a feasibility spike with a real kill criterion,
not a foundation-pour. It is useful today and nowhere near finished; this is a direction of
travel, not a legally binding promise made to a spreadsheet. The `README` roadmap is the source
of truth for what has shipped — this page adds the entry/exit criteria and kill switches behind
each step.

## Shipped

| Phase | What landed | Status | Exit / kill criterion |
|---|---|---|---|
| **0 — Data-feasibility spike** | men's senior full-international ingest; deterministic candidate models; one reproducible seal → score path; chronological evaluation; cited provenance | ✅ shipped | Exit: provenance, schema, determinism, leakage, and chronological-evaluation gates pass. Kill: accepted open data or a calibration-first baseline proves unusable |
| **1–2 — Engine + leagues** | expanded evaluation harness; the top-5 European club leagues accepted where seasons are complete; Match Search over the full ~75k-match index; per-match Commentator's Notebook computed at the pre-kickoff horizon | ✅ shipped — historical only | Exit: calibration within bands; abstention gates fire correctly; performance & a11y budgets met. Kill: calibration unfixable in the chosen scope |
| **3 — Forward loop** | real international seal-before-kickoff → score/void-after-result workflow and the forward calibration record; **in-app sealing** via `POST /api/v1/matches/{id}/seal` (v0.2.4) | ✅ shipped | Exit: a genuine matchday sealed and scored, seal invariants enforced |
| **4 — Desktop + release** | Tauri 2 shell + frozen PyInstaller sidecar; DMG / MSI / EXE + `SHA256SUMS`; docs site; consent-first signed in-app updater (v0.2.1+) | ✅ shipped, **OS-unsigned** | Exit: install/update/rollback matrix green on macOS + Windows. Code signing and notarization remain **gated on secrets not yet configured** |
| **5 — AI Analyst Read** | optional evidence-bounded narration — local-first (Ollama / llama.cpp) then BYOK cloud — with the full AI contract (deterministic evidence bundle, numeric whitelist, no chain-of-thought, injection defenses, local-only fallback) and a CI red-team suite | ✅ shipped, **off by default** | AI explains and cites the engine's numbers; it never changes one and does not improve accuracy. See [AI providers](/Golavo/ai/providers/) |
| **7 — Fact engine** | deterministic Commentator's Notebook; labelled predictive / context / coincidence; quarantined coincidences; signature form stats (v0.3.1) | ✅ shipped | Machine-checked no-write invariant holds |
| **8 — Exact scores** | coherent exact-score matrix plus Casual / Expert presentation | ✅ shipped | Machine-checked coherence: the grid marginalizes back to the sealed W/D/L and expected goals |
| **9 — Match Cockpit** | Games-first home (recent + upcoming rails, search, league chips); on-demand **Replay / Preview** model council for any indexed match at `kickoff − 1s`; Leagues browse hub; Model Lab (Track record, Backtests, Methodologies, Sealed forecasts) | ✅ shipped | Leak-safety machine-checked; nothing averaged into a consensus; nothing sealed by the cockpit itself |

## Next (planned)

- **Live club fixtures & a club forward loop** — a user-initiated data refresh, then forward
  sealing for clubs once a lawful, licensed forward source is verified.
- **League Outlook** — standings and season projections for the browse hub.
- **Observed match data** — lawful, licensed xG / lineups / injuries as typed features, only if
  the source terms permit; confirmed-lineup forecasts via BYOK depth.
- **Scorers & corners** — an internationals scorer module first (CC0); club scorers/corners only
  if a lawful data source is verified.
- **Dossiers** — team / player / manager profiles from Wikidata + CC0.
- **Longevity** — a hash-chained multi-artifact ledger, signed community packs, i18n, an ODbL
  overlay opt-in, and a signed, notarized public release.

Each planned phase carries its own entry/exit criteria, tests, defer list, and kill switch in the
planning docs. No fabricated capabilities ship: live club fixtures, standings, season
projections, and observed xG/lineups/injuries are **not** in the product today.
