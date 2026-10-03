import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET")
SCORER_URL = os.getenv("SCORER_URL", "").rstrip("/")
SCORER_TIMEOUT_SECONDS = float(os.getenv("SCORER_TIMEOUT_SECONDS", "30"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

if "*" in ALLOWED_ORIGINS:
    raise RuntimeError("ALLOWED_ORIGINS must list exact origins; wildcards are not allowed")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be set in the environment or .env file")

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET must be set in the environment or .env file")

if len(JWT_SECRET.encode("utf-8")) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 bytes long")

if SCORER_TIMEOUT_SECONDS <= 0:
    raise RuntimeError("SCORER_TIMEOUT_SECONDS must be greater than zero")
