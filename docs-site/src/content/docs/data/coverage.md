---
title: Coverage
description: An honest, competition-by-competition audit of what Golavo can and cannot show — and where the data comes from.
---

This is the honest version. Open-core data is **results-grade and redistributable**. Depth — lineups, injuries, corners, xG — is **bring-your-own-key (BYOK)**: it renders only in your private local session and is never redistributed. **Free access is not the same as open data.**

Sources were verified against their primary pages on **2026-07-09**.

## Legend

- **✅ Open** — CC0/CC-BY, redistributable, ships in the open core.
- **🔑 BYOK** — requires your own provider key; private/local display only.
- **🧱 Overlay** — separate, isolated ODbL pack (never merged into the CC0 core).
- **🟡 Partial** — some seasons/fields only.
- **🚫 Unavailable** — no lawful free source found.

## Freshness of the open core

| Source | Scope | Freshness (verified 2026-07-09) |
|---|---|---|
| openfootball | club fixtures/results | season-to-weekly lag (last push 2026-05-30; 2025-26 files present) |
| martj42/international_results | internationals: results, scorers, shootouts | ~48h (updated mid-World-Cup 2026) |
| football-data.org (free, BYOK) | 12 competitions | "scores delayed" |

## Competition ledger

| Competition | Results / tables | Goalscorers | Lineups · injuries · corners · xG |
|---|---|---|---|
| **World Cup / Euros / Copa América / AFCON / Asian Cup / Nations League + qualifiers** | ✅ Open (CC0) | ✅ Open (CC0) | 🔑 BYOK / 🚫 xG |
| **Premier League** | ✅ Open (delayed) | 🔑 BYOK | 🔑 BYOK · 🚫 xG in open core |
| **La Liga / Bundesliga / Serie A / Ligue 1** | ✅ Open (delayed) | 🔑 BYOK | 🔑 BYOK · 🚫 xG |
| **Bundesliga / DFB-Pokal (extra)** | 🧱 Overlay (OpenLigaDB, ODbL) | 🧱 Overlay | 🚫 |
| **Champions League** | ✅ Open | 🔑 BYOK | 🔑 BYOK |
| **Europa League / Conference League** | 🟡 BYOK | 🔑 BYOK | 🔑 BYOK |
| **Domestic cups (FA Cup, EFL Cup, Copa del Rey, Coppa Italia, Coupe de France)** | 🟡 Partial / BYOK | 🔑 BYOK | 🔑 BYOK |
| **Club World Cup** | 🟡 BYOK | 🔑 BYOK | 🔑 BYOK |

## The three things this table is telling you

1. **Internationals are the flagship.** Results, scorers, and shootouts are open (CC0) and fresh — the strongest open-core coverage Golavo has.
2. **Club coverage is results-grade in the open core.** Lineups, injuries, and corners require your own key.
3. **xG appears nowhere in the open core.** There is no lawful free xG source; the only open event data (Wyscout, CC BY) is frozen at the 2017/18 season and is used for model development only.

See [Sources & licenses](/Golavo/data/sources/) for the field-level license matrix and attribution requirements.
