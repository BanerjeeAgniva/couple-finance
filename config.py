"""Environment configuration and app-wide constants.

Imported by every layer; imports nothing internal (so there are no cycles).
"""
import os
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", "couple_finance.db")
PASSWORD = os.environ.get("APP_PASSWORD", "changeme")
SECRET = os.environ.get("SECRET_KEY", "dev-secret-change-me")
OCR_KEY = os.environ.get("OCR_SPACE_API_KEY", "")
STATIC = Path(__file__).parent / "static"

# Turso (card-free hosted SQLite). Set both env vars in prod; unset locally -> plain sqlite3.
TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

DEFAULT_CATEGORIES = ["Rent", "Groceries", "Eating out", "Utilities",
                      "Transport", "Shopping", "Other"]
