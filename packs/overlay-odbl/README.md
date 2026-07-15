# overlay-odbl pack

An **optional, isolated** overlay built from **OpenLigaDB** data, which is under
the **Open Database License (ODbL) 1.0**.

Scope in v1: display-only Bundesliga 1/2/3 and DFB-Pokal fixtures/results from
the current season. Golavo ships the adapter and policy, not OpenLigaDB response
bytes. A user must accept the disclosure and opt in before the sidecar fetches.

## Rules

1. This pack lives in its **own database file** and is **never joined** into the
   CC0 warehouse.
2. Any adapted database published from it must carry ODbL attribution and honor
   ODbL share-alike.
3. Displayed "produced works" must include the ODbL notice.
4. It is **opt-in** — users choose to enable the overlay.
5. V1 never supplies model inputs, probabilities, seals, settlement, calibration,
   exports, or a merged identity table. Team ids remain OpenLigaDB-local.

The executable policy is [`policy.json`](policy.json). Runtime data lives only
under the user's Application Support directory at
`overlays/openligadb/generations/<content-id>/`; deleting the overlay removes
that entire isolated subtree without touching Golavo's ledger or CC0 refresh.

Data is community-maintained; treat freshness and accuracy as community-grade and
surface that in Data & Model Health.
