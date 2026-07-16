# Phase 5 followed-match acceptance

Date: 2026-07-15
Scope: local-first followed matches and consent-gated while-open notifications

## Product boundary

- Following is stored locally under `ledger/follows/follows.sqlite3`.
- It does not enable approved-source refresh or notification permission.
- Automatic source work reuses `off`, `check_only` and `auto_refresh`.
- Followed scope narrows the source revision preflight only. A changed source
  still requires the complete Phase 1 generation before atomic activation.
- OpenLigaDB is rejected from the core follow namespace.
- No helper, Login Item, LaunchAgent, tray process or closed-app scheduler was
  added.
- Following and reconciliation never edit or settle a sealed forecast.

## Automated verification

- Server suite: 309 passed, including persistence, routes, exact identity repointing,
  unresolved-identity failure, structured refresh conflicts, settlement
  availability, notification claims, ODbL rejection and packaging isolation.
- Core deterministic suite: 317 passed.
- UI unit suite: 137 passed.
- Complete Playwright accessibility/overflow/workflow suite: 136 passed.
- Phase 5 checks include separate card link/button controls, disabled and
  honestly labelled browser-preview following, and exact closed-app Settings
  disclosures passed.
- Desktop Rust tests: 7 passed.
- Ruff, provenance, source registry, context pack, artifact and structured
  license-isolation validators passed.

## Packaged application

`packaging/build.sh aarch64-apple-darwin` completed and produced:

- `Golavo.app`: 315 MB, matching the established Phase 4 app footprint.
- `Golavo_0.13.0_aarch64.dmg`: 312 MB.
- Frozen sidecar smoke: health, search, notebook, display context and the
  internationals pack passed at version 0.13.0.
- The built app launched its bundled sidecar from the expected bundle path.
- Quitting the test bundle removed both its bootloader and Python sidecar
  processes. The separately installed `/Applications/Golavo.app` process was
  not touched.

The Mac was locked during the final UI-control attempt, so a screenshot and the
manual notification allow/deny interaction were not claimed as completed.
Permission was not requested automatically. Those two visual/manual checks
remain release-candidate QA; the plugin registration, minimal capabilities,
explicit-click request path and denied/unsupported unit paths are automated.

## Manual installed-app checklist

1. Follow and unfollow from Matchday and Match Detail.
2. Quit and relaunch; confirm subscriptions and history persist.
3. Confirm policy `off` performs no automatic source request.
4. Confirm offline history remains readable.
5. In Settings, click **Enable local notifications** and exercise both allow and
   deny paths. No prompt may appear before that click.
6. With Golavo running but unfocused, produce a fixture change against a local
   test source and confirm the generic notification contains no match details.
7. Quit Golavo and confirm no Golavo helper or test-bundle sidecar remains.
8. Confirm a structured source conflict retains the active fixture and leaves
   the sealed artifact byte-identical.

## Forbidden release claims

Do not claim live, real-time, after-quit monitoring, guaranteed delivery,
automatic settlement or current club fixtures without verified source
capability.
