# Developer shortcuts. Run from this directory (hybrid_cloud_storage_optimizer/).
.PHONY: format check test all install-hooks

format:            ## Auto-format (black) and auto-fix lint (ruff)
	uv run black .
	uv run ruff check . --fix

check:             ## Verify formatting & lint without modifying files (matches CI)
	uv run ruff check .
	uv run black --check .

test:              ## Run the deterministic test suite
	uv run pytest -q

all: format test   ## Format, then test

install-hooks:     ## Install the git pre-commit hooks
	uv run pre-commit install --config ../.pre-commit-config.yaml
