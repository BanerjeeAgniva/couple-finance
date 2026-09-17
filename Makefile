.PHONY: run test lint install

install:
	pip install -r requirements.txt

run:
	APP_PASSWORD=$${APP_PASSWORD:-changeme} SECRET_KEY=$${SECRET_KEY:-dev-secret} uvicorn app:app --reload

test:
	python test_money.py
	python test_app.py

lint:
	ruff check .
