import os
from pathlib import Path

from pydantic_settings import BaseSettings
from functools import lru_cache


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

    model_config = {
        "env_file": _find_env_file(),
        "env_file_encoding": "utf-8",
    }


@lru_cache
def get_settings():
    return Settings()
