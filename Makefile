.PHONY: setup dev ingest evaluate test lint validate build clean release-bump

setup:  ## Install core + server + ui + docs dev dependencies
	python -m pip install -e "core[dev]" || python -m pip install -e core
	python -m pip install -e "server[dev]"
	cd ui && npm install
	cd docs-site && npm install

dev:  ## Run the source-mode app (server + ui)
	@echo "Golavo — source mode. Run these in two terminals during Phase 0-1:"
	@echo "  1) uvicorn golavo_server.main:app --host 127.0.0.1 --port 8000 --app-dir server"
	@echo "  2) cd ui && npm run dev"

test:  ## Run the Python test suite
	pytest -q

ingest:  ## Materialize the pinned internationals snapshot as Parquet
	python -m golavo_core ingest

evaluate:  ## Regenerate frozen chronological evaluation artifacts
	python -m golavo_core evaluate

validate:  ## Validate provenance and every canonical sample artifact
	python scripts/validate_provenance.py
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
