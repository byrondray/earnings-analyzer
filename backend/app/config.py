import logging
import os
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = ["DATABASE_URL", "ANTHROPIC_API_KEY", "BRAVE_SEARCH_API_KEY"]


def _find_env_file() -> str | None:
    candidates = [Path("../.env"), Path(".env")]
    for p in candidates:
        if p.is_file():
            return str(p)
    return None


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    REDIS_URL: str = ""
    FMP_API_KEY: str = ""
    ALPHA_VANTAGE_API_KEY: str = ""
    NEWS_API_KEY: str = ""
    POLYGON_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    BRAVE_SEARCH_API_KEY: str = ""
    CLERK_SECRET_KEY: str = ""
    CLERK_JWKS_URL: str = ""

    model_config = {
        "env_file": _find_env_file(),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def _warn_missing_keys(self):
        missing = [k for k in _REQUIRED_KEYS if not getattr(self, k)]
        if missing:
            logger.warning("Missing required env vars: %s", ", ".join(missing))
        return self


@lru_cache
def get_settings():
    return Settings()
