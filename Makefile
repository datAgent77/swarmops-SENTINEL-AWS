# SwarmOps developer commands. Run from the repository root.
# Backend uses a local virtualenv at apps/api/.venv.

API := apps/api
WEB := apps/web
ACT := . .venv/bin/activate

# Local database names / role (match the default DATABASE_URL).
DB_NAME := swarmops
DB_TEST := swarmops_test
DB_ROLE := swarmops

.PHONY: install db-create lint test build migrate seed db-reset api web demo verify snapshot help

help:
	@echo "make install    - install backend (venv) and frontend deps"
	@echo "make db-create  - create the '$(DB_ROLE)' role + '$(DB_NAME)'/'$(DB_TEST)' databases"
	@echo "make migrate    - run database migrations (alembic upgrade head)"
	@echo "make seed       - seed organization, agents, and policies"
	@echo "make demo       - migrate + seed, then run BOTH servers (one command, Ctrl-C stops)"
	@echo "make lint       - lint backend (ruff) and frontend (eslint)"
	@echo "make test       - run backend test suite (pytest)"
	@echo "make build      - production build of the frontend"
	@echo "make api        - run the API dev server on :8000  (terminal 1)"
	@echo "make web        - run the frontend dev server on :3000  (terminal 2)"
	@echo "make db-reset   - drop, re-migrate, and re-seed the database"
	@echo "make verify     - run the end-to-end happy-path integration test"
	@echo "make snapshot   - write a dated BUILD.md + dist zip for submission"

install:
	cd $(API) && python3 -m venv .venv && $(ACT) && pip install -U pip && pip install -r requirements-dev.txt
	cd $(WEB) && npm install

# One-shot local database setup. Assumes a local Postgres where 'psql postgres'
# connects as a superuser (the default on Postgres.app / Homebrew). Idempotent.
db-create:
	@psql postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$(DB_ROLE)'" | grep -q 1 \
		|| psql postgres -c "CREATE ROLE $(DB_ROLE) LOGIN SUPERUSER;"
	@createdb $(DB_NAME) 2>/dev/null || true
	@createdb $(DB_TEST) 2>/dev/null || true
	@echo "Ready: role '$(DB_ROLE)', databases '$(DB_NAME)' and '$(DB_TEST)'."

migrate:
	cd $(API) && $(ACT) && alembic upgrade head

seed:
	cd $(API) && $(ACT) && python -m app.seed

lint:
	cd $(API) && $(ACT) && ruff check app tests
	cd $(WEB) && npm run lint

test:
	cd $(API) && $(ACT) && python -m pytest

build:
	cd $(WEB) && npm run build

api:
	cd $(API) && $(ACT) && uvicorn app.main:app --reload --port 8000

web:
	cd $(WEB) && npm run dev

# One command for demo day: apply migrations, seed, then run both servers
# together (Ctrl-C stops both). Assumes `make install` + `make db-create` were run.
demo: migrate seed
	bash scripts/dev.sh

# Dated build snapshot for hackathon submission (BUILD.md + dist/ zip).
snapshot:
	bash scripts/snapshot.sh

db-reset:
	cd $(API) && $(ACT) && alembic downgrade base && alembic upgrade head && python -m app.seed

verify:
	cd $(API) && $(ACT) && python -m pytest tests/test_api.py -q
