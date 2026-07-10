---
title: Contributing
description: How to contribute, and the non-negotiable rules that keep Golavo honest and legal.
---

Contributions are welcome. The authoritative guide is [CONTRIBUTING.md](https://github.com/udhawan97/Golavo/blob/main/CONTRIBUTING.md) in the repository; the essentials are here.

## Golden rules

1. **The statistical engine owns every probability.** UI, docs, and AI never invent or "adjust" a number.
2. **Every displayed fact carries a source id.** No source, no ship.
3. **Never commit proprietary or user data** — no football-data.org / API-Football responses, no StatsBomb data, no scraped feeds. Only CC0/CC-BY, and only small frozen demo fixtures.
4. **ODbL stays isolated.** OpenLigaDB data/code never joins the CC0 core; CI enforces this.
5. **Golavo is not a betting product** — no odds, "value," "units," "locks," or affiliate links, in code or copy.

## Workflow

- Branch from `main` (`feat/…`, `fix/…`, `docs/…`).
- Use Conventional Commits and sign off (`git commit -s`).
- Any model change ships with a backtest and its effect on out-of-sample RPS / log loss.
- Fill in the PR template; all CI checks must be green.

Security issues go through private reporting — see the repository's `SECURITY.md`, not a public issue.
