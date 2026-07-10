<!-- Thanks for contributing to Golavo. Keep PRs focused. -->

## What & why

<!-- What does this change, and what problem does it solve? Link issues: Closes #123 -->

## Type

- [ ] feat  - [ ] fix  - [ ] docs  - [ ] refactor  - [ ] test  - [ ] chore

## Checklist

- [ ] `make test` / `make lint` pass locally (or CI is green).
- [ ] Commits are signed off (`git commit -s`) and follow Conventional Commits.
- [ ] No proprietary/user data, API keys, or scraped feeds are included.
- [ ] ODbL (OpenLigaDB) data/code stays isolated from the CC0 core.

## If this touches the model

- [ ] Includes/updates a backtest.
- [ ] States the effect on out-of-sample RPS / log loss (no accuracy claims without forward evidence).

## If this touches the AI layer

- [ ] AI cannot introduce a number absent from its evidence bundle.
- [ ] No chain-of-thought is exposed in the UI.
