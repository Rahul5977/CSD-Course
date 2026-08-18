# Every routine operation has one command here, so the installation guide is a
# list of make targets rather than a page of prose. `make help` lists them.

COMPOSE := docker compose -f infra/docker-compose.yml
UV      := uv run

.DEFAULT_GOAL := help
.PHONY: help install up down logs ps shell seed migrate revision test test-cov lint fmt typecheck check clean

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Create the virtualenv and install all dependencies
	uv sync
	@echo "Copy .env.example to .env if you want to override defaults."

up:  ## Build and start the stack, then apply migrations
	$(COMPOSE) up -d --build
	@echo "Waiting for the API to report healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' pond-planner-api-1 2>/dev/null)" = "healthy" ]; do sleep 2; done
	$(COMPOSE) exec -T api alembic upgrade head
	@echo "Swagger UI: http://localhost:$${POND_API_PORT:-8000}/docs"

down:  ## Stop the stack (add ARGS=-v to also drop the volumes)
	$(COMPOSE) down $(ARGS)

logs:  ## Tail logs from every service
	$(COMPOSE) logs -f --tail=100

ps:  ## Show service status
	$(COMPOSE) ps

shell:  ## Open a shell in the api container
	$(COMPOSE) exec api /bin/bash

seed:  ## Load demo data (village boundary, sample contour map)
	@echo "Not implemented until P1 — the seed needs a village boundary first."
	@exit 1

migrate:  ## Apply migrations to the running database
	$(COMPOSE) exec -T api alembic upgrade head

revision:  ## Autogenerate a migration: make revision M="add rainfall tables"
	@test -n "$(M)" || (echo 'Usage: make revision M="message"' && exit 1)
	$(COMPOSE) exec -T api alembic revision --autogenerate -m "$(M)"

test:  ## Run the test suite
	$(UV) pytest

test-cov:  ## Run tests with a coverage report (G7 needs >= 70% on engines/ and domain/)
	$(UV) pytest --cov --cov-report=term-missing --cov-report=html

lint:  ## Check formatting and lint rules
	$(UV) ruff format --check .
	$(UV) ruff check .

fmt:  ## Auto-format and auto-fix
	$(UV) ruff format .
	$(UV) ruff check --fix .

typecheck:  ## Type-check (strict on app/domain and app/engines)
	$(UV) mypy

check: lint typecheck test  ## Everything CI runs

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +
