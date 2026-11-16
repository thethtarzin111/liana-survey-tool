# CI only calls these targets, so the pipeline is easy to move to GitLab CI.
# On Windows, run them from Git Bash or WSL (or copy the commands).

PY_DIRS := backend/shared-py backend/survey-manager backend/respondent backend/data-analyzer \
           backend/worker backend/liana-connector
PIP     ?= python -m pip

.PHONY: install install-py install-web lint lint-py lint-web test test-py test-web \
        up down logs migrate seed e2e

install: install-py install-web

install-py:
	$(PIP) install -e "backend/shared-py[dev,web]"
	$(PIP) install -e "backend/survey-manager[dev]" -e "backend/respondent[dev]" -e "backend/data-analyzer[dev]" \
	  -e "backend/worker[dev]" -e "backend/liana-connector[dev]"

install-web:
	cd frontend && npm ci

lint: lint-py lint-web

lint-py:
	ruff check $(PY_DIRS)
	ruff format --check $(PY_DIRS)

lint-web:
	cd frontend && npm run typecheck && npm run lint

test: test-py test-web

test-py:
	@for d in $(PY_DIRS); do echo "== $$d"; (cd $$d && python -m pytest -q) || exit 1; done

test-web:
	cd frontend && npm test

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

migrate:
	docker compose run --rm migrate

seed:
	docker compose run --rm seed

e2e:
	cd tests/e2e && npm ci && npx playwright install --with-deps chromium && npx playwright test
