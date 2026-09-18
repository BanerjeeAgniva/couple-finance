.PHONY: run test lint typecheck audit install install-dev hooks

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

run:
	APP_PASSWORD=$${APP_PASSWORD:-changeme} SECRET_KEY=$${SECRET_KEY:-dev-secret} uvicorn app:app --reload

test:
	python test_money.py
	python test_app.py

lint:
	ruff check .

typecheck:
	mypy

audit:
	pip-audit

hooks:
	pre-commit install
