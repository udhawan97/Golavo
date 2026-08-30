---
title: Transfer Desk
description: How Golavo reads bounded, provider-attributed club transfers without inventing fee structure or model evidence.
---

Transfer Desk is an optional, foreground-only view of arrivals and departures for clubs in
Golavo's five certified domestic leagues. It is a separate Sportmonks BYOK capability. Merely
opening the page, selecting a club, or enabling the connector does not fetch transfer data.

![Transfer Desk before an explicit provider fetch, showing exact club selection, foreground-only access, and the payment evidence boundary](/Golavo/screenshots/transfer-desk.png)

The screenshot shows the honest source-preview state: club identities come from the local fixture
index, while provider rows remain absent until the separately enabled installed-app route receives an
explicit click and valid user-supplied access.

## Fetch one club

1. Open **Settings → Sources**, review the Sportmonks disclosure, and add your own token.
2. Separately enable **Top-five league Transfer Desk**.
3. Open **Leagues → Transfer Desk** and choose a club from exact local current-season fixture
   identities.
4. Select **Fetch transfer window**.

Golavo first matches an exact provider fixture, league, season, home/away team name, and distinct
numeric team identity. It then requests only that team's documented transfer endpoint, in descending
date order, for at most four pages of 50 rows. The requested window is the preceding 365 days. If the
page limit is reached before the date window closes, the result is visibly **partial**.

## What a row means

Each promoted row keeps the provider's transfer, player, transfer-type, position, from-team, and
to-team identities. It shows transfer date, direction, provider completion state, and the provider's
nullable amount string.

The amount is labelled **provider-reported amount — currency unspecified**. Golavo preserves the
string verbatim. It does not turn it into a numeric fee, infer a currency, total a window, or compare
it with another source.

The feed does not provide a structured payment breakdown, so these fields are always explicit
unavailable states:

- currency;
- installments;
- add-ons;
- sell-on terms;
- agent or intermediary fees;
- training rewards; and
- conditional consideration.

A real payment breakdown would require reviewed primary club or issuer disclosures for that exact
transaction. Transfer rumours, logos/photos, scraped sites, and undocumented endpoints are excluded.

## Data and model boundary

Every fetch records its time, requested window, page coverage, provider fixture/team identity, terms
version, and raw-response hashes in the in-memory response. Raw provider bytes are not stored.

Transfer records cannot enter Golavo model fitting, forecasts, seals, settlement, scoring,
calibration, AI evidence, picks, or exports. Disabling or disconnecting Sportmonks aborts live
requests and clears the response from the interface. See [Privacy & security](/Golavo/privacy-security/)
for the full connector boundary.

:::caution[Provider access is not bundled]
Transfer Desk requires the user's own Sportmonks token, plan, league entitlement, and any relevant
add-on. Golavo's fixture-based tests prove the parser and failure behavior; they do not claim that a
particular account currently has live access.
:::
