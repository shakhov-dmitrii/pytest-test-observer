UV ?= uv
CH_PASSWORD ?=

.PHONY: help install test lint format coverage build clean smoke example

install: 
	$(UV) sync

test:
	$(UV) run pytest -v

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

coverage:
	$(UV) run coverage run -m pytest -q
	$(UV) run coverage report

build:
	$(UV) build

clean:
	rm -rf dist build .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +

smoke: ## Run the test suite against the local ClickHouse
	$(UV) run pytest tests/ --ch-url=localhost:8123 --ch-table=smoke -v
	docker exec pytest-test-observer-clickhouse clickhouse-client \
	  --password "$(CH_PASSWORD)" \
	  -q "SELECT nodeid, status, allure_severity FROM default.smoke ORDER BY started_at LIMIT 10 FORMAT PrettyCompact"

example:
	cd examples/basic && $(UV) sync && ($(UV) run pytest -v || true)
