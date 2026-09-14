.PHONY: run test lint typecheck audit install install-dev hooks

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

run:
	APP_PASSWORD=$${APP_PASSWORD:-changeme} SECRET_KEY=$${SECRET_KEY:-dev-secret} uvicorn app:app --reload

test:
	python -m tests.test_money
	python -m tests.test_app

lint:
	ruff check .

typecheck:
	mypy

audit:
	pip-audit

hooks:
	pre-commit install
