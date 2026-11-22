.PHONY: up down logs test test-backend test-frontend lint backfill histogram boundaries pipeline taxonomy dev-api dev-web

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

histogram:     ## Import an eBird bar chart file: make histogram FILE=/path/to/file.txt
	@test -f "$(FILE)" || { echo "usage: make histogram FILE=/path/to/ebird_..._barchart.txt"; exit 1; }
	docker compose run --rm -T api python -m app.cli import-histogram /dev/stdin --filename "$$(basename "$(FILE)")" < "$(FILE)"

boundaries:    ## Label private locations: make boundaries [AREA="Hotspot name prefix"]
	@test -d data/census || { echo "Put the Census place and cousub zips in data/census (see README)"; exit 1; }
	docker compose run --rm -v "$(CURDIR)/data/census:/census:ro" api python -m app.cli import-boundaries /census --hotspot-area "$(AREA)"

backfill:      ## Legacy v1 history fetch; see README before using
	docker compose run --rm api python -m app.cli backfill --years 3

pipeline:      ## Run the scheduled pipeline once, right now
	docker compose run --rm api python -m app.cli run-pipeline

dev-api:       ## Run the API locally against SQLite, no Docker
	cd backend && uv run alembic upgrade head && uv run uvicorn app.api.main:app --reload

dev-web:
	cd frontend && npm run dev
