.PHONY: run test lint typecheck audit install install-dev hooks ui ui-setup

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

run:
	APP_PASSWORD=$${APP_PASSWORD:-changeme} SECRET_KEY=$${SECRET_KEY:-dev-secret} uvicorn app:app --reload

test:
	python -m tests.test_money
	python -m tests.test_insights_engine
	python -m tests.test_app
	python -m tests.test_handlers

ui-setup:
	python -m playwright install chromium

ui:
	python -m tests.test_ui

lint:
	ruff check .

typecheck:
	mypy

audit:
	pip-audit

hooks:
	pre-commit install
