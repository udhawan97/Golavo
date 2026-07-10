# data/fixtures

**Frozen, lawful, CC0-only** demo bundles used by the documentation site,
screenshots, and tests. These are the *only* data files tracked in the repo.

Rules:

- CC0 sources only (openfootball, martj42, Wikidata). No BYOK data, no ODbL data,
  no StatsBomb data, no scraped feeds.
- Small and frozen — a handful of matches, pinned by snapshot hash, never
  auto-refreshed.
- Used to demonstrate a full sealed-forecast → after-the-whistle flow without any
  provider key or live backend (this is what the public website renders).

Runtime user data (the warehouse, ledger, and settings) lives in the OS
app-data directory and is never committed — see `.gitignore`.
