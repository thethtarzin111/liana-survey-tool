# CI only calls these targets, so the pipeline is easy to move to GitLab CI.
# On Windows, run them from Git Bash or WSL (or copy the commands).

PY_DIRS := backend/packages/shared-py backend/services/survey-manager backend/services/respondent backend/services/data-analyzer \
           backend/services/worker backend/services/liana-connector
PIP     ?= python -m pip

.PHONY: install install-py install-web lint lint-py lint-web test test-py test-web \
        up down logs migrate seed e2e

install: install-py install-web

install-py:
	$(PIP) install -e "backend/packages/shared-py[dev,web]"
	$(PIP) install -e "backend/services/survey-manager[dev]" -e "backend/services/respondent[dev]" -e "backend/services/data-analyzer[dev]" \
	  -e "backend/services/worker[dev]" -e "backend/services/liana-connector[dev]"

install-web:
	cd frontend && npm ci

lint: lint-py lint-web

lint-py:
	ruff check $(PY_DIRS) backend/scripts
	ruff format --check $(PY_DIRS) backend/scripts

lint-web:
	cd frontend && npm run typecheck && npm run lint

test: test-py test-web

test-py:
	@for d in $(PY_DIRS); do echo "== $$d"; (cd $$d && python -m pytest -q) || exit 1; done
	python -m pytest backend/scripts/tests -q

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
