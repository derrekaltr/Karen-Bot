.PHONY: help dev dev-down venv install install-web migrate test test-pg lint typecheck demo-e2e api worker

PY ?= python3
VENV := apps/api/.venv
PIP := $(VENV)/bin/pip
PYTHON := $(VENV)/bin/python

help:
	@echo "Targets:"
	@echo "  make install    - create venv, install API deps + web deps"
	@echo "  make dev        - start Postgres + MinIO via docker compose"
	@echo "  make dev-down   - stop the dev stack"
	@echo "  make migrate    - run Alembic migrations against DATABASE_URL"
	@echo "  make test       - run API test suite (SQLite, no Docker needed)"
	@echo "  make test-pg    - run full suite incl. Postgres-only tests"
	@echo "  make lint       - ruff + eslint"
	@echo "  make typecheck  - mypy + tsc"
	@echo "  make demo-e2e   - simulated end-to-end case flow (mock email + scripted LLM)"
	@echo "  make api        - run FastAPI dev server"
	@echo "  make worker     - run the scheduler/outbox worker loop"

venv:
	test -d $(VENV) || $(PY) -m venv $(VENV)

install: venv
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e "apps/api[dev]"
	npm install

dev:
	docker compose -f infra/docker-compose.yml up -d
	@echo "Postgres: localhost:5432 (karenbot/karenbot)  MinIO: localhost:9000"

dev-down:
	docker compose -f infra/docker-compose.yml down

migrate:
	cd apps/api && ../../$(VENV)/bin/alembic upgrade head

test:
	cd apps/api && .venv/bin/python -m pytest tests -q

test-pg:
	cd apps/api && KARENBOT_TEST_DATABASE_URL=postgresql+psycopg://karenbot:karenbot@localhost:5432/karenbot_test .venv/bin/python -m pytest tests -q

lint:
	cd apps/api && .venv/bin/ruff check src tests
	npm run lint --workspace apps/web --if-present

typecheck:
	cd apps/api && .venv/bin/mypy src
	npm run typecheck --workspace apps/web --if-present

demo-e2e:
	cd apps/api && .venv/bin/python -m karenbot.demo.e2e

api:
	cd apps/api && .venv/bin/uvicorn karenbot.api.main:app --reload --port 8000

worker:
	cd apps/api && .venv/bin/python -m karenbot.workflows.worker
