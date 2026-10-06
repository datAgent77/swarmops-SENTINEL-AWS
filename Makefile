# Sentinel developer commands. Run from the repository root.
# Backend uses a local virtualenv at apps/api/.venv. No database — Sentinel's
# authoritative state is in-process.

API := apps/api
WEB := apps/web
PY  := .venv/bin

.PHONY: install lint test build api web dev help

help:
	@echo "make install  - install backend (venv) and frontend deps"
	@echo "make dev      - run API (:8000) and web (:3000) together (Ctrl-C stops both)"
	@echo "make api      - run the API dev server on :8000  (terminal 1)"
	@echo "make web      - run the frontend dev server on :3000  (terminal 2)"
	@echo "make lint     - lint backend (ruff) and frontend (eslint)"
	@echo "make test     - run backend test suite (pytest)"
	@echo "make build    - production build of the frontend"

install:
	cd $(API) && python3 -m venv .venv && $(PY)/pip install -U pip && $(PY)/pip install -r requirements-dev.txt
	cd $(WEB) && npm install

lint:
	cd $(API) && $(PY)/ruff check app tests
	cd $(WEB) && npm run lint

test:
	cd $(API) && $(PY)/pytest

build:
	cd $(WEB) && npm run build

api:
	cd $(API) && $(PY)/uvicorn app.main:app --reload --port 8000

web:
	cd $(WEB) && npm run dev

# Run both servers together for a demo (Ctrl-C stops both).
dev:
	bash scripts/dev.sh
