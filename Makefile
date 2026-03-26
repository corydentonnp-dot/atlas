.PHONY: help dev up down migrate test lint format typecheck check clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev:  ## Start dev server with auto-reload
	uvicorn atlas.api.main:app --reload --host 0.0.0.0 --port 8000

up:  ## Start Docker infrastructure (Postgres + Redis)
	docker-compose up -d

down:  ## Stop Docker infrastructure
	docker-compose down

migrate:  ## Run database migrations
	alembic upgrade head

migrate-new:  ## Create a new migration (usage: make migrate-new msg="description")
	alembic revision --autogenerate -m "$(msg)"

test:  ## Run test suite
	pytest

test-cov:  ## Run tests with coverage
	pytest --cov=atlas --cov-report=html

lint:  ## Run linter
	ruff check atlas/ tests/

format:  ## Format code
	black atlas/ tests/
	ruff check --fix atlas/ tests/

typecheck:  ## Run type checker
	mypy atlas/

check: lint typecheck test  ## Run all checks (lint + typecheck + test)

clean:  ## Clean build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null; true
	rm -f .coverage

worker:  ## Start arq task worker
	arq atlas.core.tasks.worker.WorkerSettings
