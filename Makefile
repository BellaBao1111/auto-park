.DEFAULT_GOAL := help
.PHONY: help setup run pay test lint format check lock clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: ## Create .venv, install deps + tooling, and the Playwright browser
	uv sync --extra dev
	uv run playwright install chromium
	@echo "Done. Copy .env.example to .env and fill it in (chmod 600 .env)."

run: ## Run the scheduler + Telegram bot (Ctrl+C to stop)
	uv run auto-park

pay: ## Manually test the payment flow, e.g. make pay ARGS="--zone 408 --space 503 --duration 60"
	uv run python -m autopark.pay $(ARGS)

test: ## Run the test suite
	uv run pytest

lint: ## Lint with ruff
	uv run ruff check .

format: ## Auto-format with ruff
	uv run ruff format .

check: lint test ## Lint + test (what CI would run)

lock: ## Refresh uv.lock and re-export the pinned requirements.txt fallback
	uv lock
	uv export --frozen --no-dev --no-emit-project --format requirements-txt -o requirements.txt

clean: ## Remove caches and build artifacts (keeps .venv and jobs.db)
	rm -rf .pytest_cache .ruff_cache src/*.egg-info
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} +
