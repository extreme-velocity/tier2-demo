# ai-velocity-kit — one entry point for every routine task.
# CI mirrors `make lint test`. If it passes here, it passes there.
# ADJUST FOR YOUR STACK: this Makefile assumes the reference skeleton
# (python/ + typescript/). Delete or rewrite the halves you don't use —
# the CI lanes are the contract, not these targets.

.PHONY: dev lint lint-ts format test test-py test-ts release metrics clean

dev:            ## Install all deps (python + typescript)
	cd python && uv sync
	cd typescript && npm ci

lint:           ## Python lint (ruff check + format check)
	uvx ruff@0.16.5 check python/ scripts/
	uvx ruff@0.16.5 format --check python/ scripts/

lint-ts:        ## TypeScript lint (biome)
	cd typescript && npx biome check src tests

format:         ## Auto-fix formatting (what autofix.yml runs on merge)
	uvx ruff@0.16.5 check --fix python/ scripts/ && uvx ruff@0.16.5 format python/ scripts/
	cd typescript && npx biome check --write src tests || true

test: test-py test-ts  ## Run all tests

test-py:        ## Python tests
	cd python && uv run pytest -q

test-ts:        ## TypeScript tests
	cd typescript && npm ci --no-audit --no-fund >/dev/null && npm test

metrics:        ## Velocity dashboard (local)
	GH_TOKEN=$$(gh auth token) python3 scripts/repo_metrics.py --repo $(REPO) --markdown

release:        ## Cut a release (patch by default)
	python3 scripts/release.py --part $(part)

clean:
	rm -rf python/.venv python/dist typescript/node_modules typescript/dist
