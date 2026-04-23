import json
import os
import tempfile

from dotenv import load_dotenv

load_dotenv()


def _resolve_credentials():
    """Support credentials as a file path OR as inline JSON via env var."""
    inline = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
    if inline:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(inline)
        tmp.close()
        return tmp.name
    return os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")


class Config:
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-fallback-key")
    GOOGLE_CREDENTIALS_FILE = _resolve_credentials()
    GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    DEBUG = FLASK_ENV == "development"
