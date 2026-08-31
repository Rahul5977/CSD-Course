# Every routine operation has one command here, so the installation guide is a
# list of make targets rather than a page of prose. `make help` lists them.

COMPOSE := docker compose -f infra/docker-compose.yml
UV      := uv run

.DEFAULT_GOAL := help
.PHONY: help install up down logs ps shell seed migrate revision openapi test test-cov lint fmt typecheck check clean web-install web-dev web-build api-dev worker-dev figures loadtest tunnel report

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
	@for i in 1 2 3 4 5 6; do $(COMPOSE) exec -T api alembic upgrade head && break; echo "migration attempt $$i failed (database still starting?) — retrying in 5 s"; sleep 5; done
	@echo "App:        http://localhost:$${POND_WEB_PORT:-3000}"
	@echo "Grafana:    http://localhost:$${POND_GRAFANA_PORT:-3001}  (anonymous viewer; admin/$${POND_GRAFANA_PASSWORD:-admin})"
	@echo "Swagger UI: http://localhost:$${POND_API_PORT:-8000}/docs"

down:  ## Stop the stack (add ARGS=-v to also drop the volumes)
	$(COMPOSE) down $(ARGS)

logs:  ## Tail logs from every service
	$(COMPOSE) logs -f --tail=100

ps:  ## Show service status
	$(COMPOSE) ps

shell:  ## Open a shell in the api container
	$(COMPOSE) exec api /bin/bash

seed:  ## Analyse the provided sample contour map through the running stack
	@for i in $$(seq 1 30); do curl -sf http://localhost:$${POND_API_PORT:-8000}/ready >/dev/null && break; [ $$i = 30 ] && { echo "API not ready on :$${POND_API_PORT:-8000} — is the stack up? (make ps, make logs)"; exit 1; }; sleep 2; done
	@echo "Uploading data/samples/contours_1m.kml to POST /api/v1/analyzeContour ..."
	@JOB=$$(curl -sf -F "file=@data/samples/contours_1m.kml" http://localhost:$${POND_API_PORT:-8000}/api/v1/analyzeContour | python3 -c 'import sys,json;print(json.load(sys.stdin)["job_id"])'); \
	[ -n "$$JOB" ] || { echo "upload failed — see make logs"; exit 1; }; \
	echo "job $$JOB queued"; \
	for i in $$(seq 1 90); do \
	  S=$$(curl -sf http://localhost:$${POND_API_PORT:-8000}/api/v1/jobs/$$JOB); \
	  ST=$$(echo "$$S" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["status"], d["progress"], d.get("stage") or "")'); \
	  echo "  $$ST"; \
	  case "$$ST" in succeeded*) echo "done: http://localhost:$${POND_WEB_PORT:-3000}"; exit 0;; failed*|cancelled*) echo "$$S"; exit 1;; esac; \
	  sleep 2; \
	done; echo "timed out"; exit 1

migrate:  ## Apply migrations to the running database
	$(COMPOSE) exec -T api alembic upgrade head

revision:  ## Autogenerate a migration: make revision M="add rainfall tables"
	@test -n "$(M)" || (echo 'Usage: make revision M="message"' && exit 1)
	$(COMPOSE) exec -T api alembic revision --autogenerate -m "$(M)"

openapi:  ## Regenerate docs/api/openapi.json from the app (graded artifact)
	$(UV) python -c "import json;from app.main import create_app;print(json.dumps(create_app().openapi(), indent=2))" > docs/api/openapi.json
	@echo "docs/api/openapi.json regenerated — commit it with the change that altered the contract."

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

report:  ## Render docs/report/REPORT.md to REPORT.pdf (python-markdown + headless Chrome)
	uv run python scripts/make_report.py

tunnel:  ## Expose the app on a public URL through ngrok (requires `ngrok config add-authtoken …` once)
	ngrok http $${POND_WEB_PORT:-3000}

loadtest:  ## Locust: 50 users for 60 s against the running stack (records p95 into docs/figures/p6-locust.txt)
	$(UV) locust -f infra/locustfile.py --headless -u 50 -r 10 -t 60s --host http://localhost:$${POND_API_PORT:-8000} --only-summary 2>&1 | tee docs/figures/p6-locust.txt

figures:  ## Regenerate the evidence figures in docs/figures from the sample map
	$(UV) python scripts/make_figures.py
	$(UV) python scripts/make_water_figure.py
	$(UV) python scripts/make_algorithm_figures.py

check: lint typecheck test  ## Everything CI runs

e2e:  ## Smoke-test every real route against a running deployment (BASE=http://host:port, default :8000)
	$(UV) python scripts/e2e_smoke.py $${BASE:-http://localhost:8000}

serve-single:  ## API + built SPA from one uvicorn process (for hosts without Docker; run `make web-build` first)
	POND_PERSISTENCE=memory POND_JOB_RUNNER=inline POND_OBJECT_STORE=local POND_RAINFALL_SOURCE=recorded $(UV) uvicorn scripts.single_server:app --host 0.0.0.0 --port $${PORT:-8080}

api-dev:  ## Run the API locally without Docker (in-memory persistence, inline jobs, local store)
	POND_PERSISTENCE=memory POND_JOB_RUNNER=inline POND_OBJECT_STORE=local $(UV) uvicorn app.main:app --reload --port 8000

worker-dev:  ## Run a Celery worker locally against the compose redis/postgres/minio
	$(UV) celery -A app.jobs.celery_app:celery_app worker --queues interactive,heavy --loglevel INFO

web-install:  ## Install frontend dependencies
	cd web && npm ci --no-audit --no-fund

web-dev:  ## Run the frontend dev server (proxies /api → :8000, /tiles → :8080)
	cd web && npm run dev

web-build:  ## Production build of the frontend
	cd web && npm run build

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +
