import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-fallback-key")
    GOOGLE_CREDENTIALS_FILE = os.environ.get(
        "GOOGLE_CREDENTIALS_FILE", "credentials.json"
    )
    GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
