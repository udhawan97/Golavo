.PHONY: setup dev ingest index evaluate test lint validate build clean release-bump

setup:  ## Install core + server + ui + docs dev dependencies
	python -m pip install -e "core[dev]" || python -m pip install -e core
	python -m pip install -e "server[dev]"
	cd ui && npm install
	cd docs-site && npm install

dev:  ## Run the local API + browser UI (Ctrl+C stops both)
	python scripts/dev.py

test:  ## Run the Python test suite
	pytest -q

ingest:  ## Materialize the pinned internationals snapshot as Parquet
	python -m golavo_core ingest

index:  ## Build the committed, deterministic match search index (all packs + side tables)
	python -m golavo_core index

evaluate:  ## Regenerate frozen chronological evaluation artifacts
	python -m golavo_core evaluate

validate:  ## Validate provenance and every canonical sample artifact
	python scripts/validate_provenance.py
	python scripts/validate_sources.py
	python scripts/validate_context_pack.py
	python scripts/validate_license_isolation.py
	python scripts/validate_correction_isolation.py
	python scripts/validate_research_isolation.py
	python scripts/validate_artifacts.py

lint:  ## Lint python + ui
	ruff check .
	cd ui && npm run lint --if-present

build:  ## Build the UI and docs site
	cd ui && npm run build
	cd docs-site && npm run build

release-bump:  ## Sync the project version everywhere (VERSION=x.y.z), then verify agreement
	python scripts/bump_version.py "$(VERSION)"

clean:  ## Remove build output and caches
	rm -rf ui/dist docs-site/dist docs-site/.astro
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
