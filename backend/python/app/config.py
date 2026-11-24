import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR.parent / ".env")

REQUIRED_SETTINGS = (
    "DATABASE_URL",
    "MPESA_BASE_URL",
    "MPESA_CONSUMER_KEY",
    "MPESA_CONSUMER_SECRET",
)


class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    MPESA_BASE_URL = os.getenv("MPESA_BASE_URL", "").rstrip("/")
    MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "")
    MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "")
    MPESA_TIMEOUT = int(os.getenv("MPESA_TIMEOUT", "30"))
    QR_CODE_DIR = Path(os.getenv("QR_CODE_DIR", str(BASE_DIR / "qrcodes")))
    DB_POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
    DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "10"))
    MAX_CONTENT_LENGTH = 1024 * 1024


def validate_config(config):
    missing = [name for name in REQUIRED_SETTINGS if not str(config.get(name) or "").strip()]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
