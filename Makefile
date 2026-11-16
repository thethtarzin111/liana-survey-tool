# CI only calls these targets, so the pipeline is easy to move to GitLab CI.
# On Windows, run them from Git Bash or WSL (or copy the commands).

PY_DIRS := packages/shared-py services/survey-manager services/respondent services/data-analyzer \n           services/worker services/liana-connector
PIP     ?= python -m pip

.PHONY: install install-py install-web lint lint-py lint-web test test-py test-web \
        up down logs migrate seed e2e

install: install-py install-web

install-py:
	$(PIP) install -e "packages/shared-py[dev,web]"
	$(PIP) install -e "services/survey-manager[dev]" -e "services/respondent[dev]" -e "services/data-analyzer[dev]" \n	  -e "services/worker[dev]" -e "services/liana-connector[dev]"

install-web:
	cd apps/admin-web && npm ci

lint: lint-py lint-web

lint-py:
	ruff check $(PY_DIRS)
	ruff format --check $(PY_DIRS)

lint-web:
	cd apps/admin-web && npm run typecheck && npm run lint

test: test-py test-web

test-py:
	@for d in $(PY_DIRS); do echo "== $$d"; (cd $$d && python -m pytest -q) || exit 1; done

test-web:
	cd apps/admin-web && npm test

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
