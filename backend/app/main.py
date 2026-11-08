"""FastAPI application entry point."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.api.health import router as health_router
from app.api.router import api_router

BACKEND_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_backend_environment(env_file: Path | None = None) -> None:
    """Load local backend settings without overriding process-level configuration."""
    load_dotenv(env_file or BACKEND_ENV_FILE, override=False)


load_backend_environment()

DEFAULT_ALLOWED_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def get_allowed_origins() -> list[str]:
    """Read development origins from the comma-separated UDYAMONE_ALLOWED_ORIGINS."""
    configured_origins = os.getenv("UDYAMONE_ALLOWED_ORIGINS")
    if not configured_origins:
        return list(DEFAULT_ALLOWED_ORIGINS)
    origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
    return [origin for origin in origins if origin != "*"] or list(DEFAULT_ALLOWED_ORIGINS)


app = FastAPI(title="UdyamOne API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
import os
...
app.include_router(health_router)
app.include_router(api_router)
if os.getenv("UDYAMONE_QA_MODE") == "1":
    from app.api.qa import router as qa_router

    app.include_router(qa_router)
