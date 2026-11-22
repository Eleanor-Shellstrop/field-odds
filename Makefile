.PHONY: up down logs test test-backend test-frontend lint backfill pipeline taxonomy dev-api dev-web

up:            ## Start db, api, worker and web
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api worker

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && npm test

lint:
	cd backend && uv run ruff check . && uv run mypy app
	cd frontend && npm run lint && npm run type-check

taxonomy:      ## Load eBird taxonomy (species names) into the db
	docker compose run --rm api python -m app.cli seed-taxonomy

backfill:      ## Legacy v1 history fetch; see README before using
	docker compose run --rm api python -m app.cli backfill --years 3

pipeline:      ## Run the scheduled pipeline once, right now
	docker compose run --rm api python -m app.cli run-pipeline

dev-api:       ## Run the API locally against SQLite, no Docker
	cd backend && uv run alembic upgrade head && uv run uvicorn app.api.main:app --reload

dev-web:
	cd frontend && npm run dev
