from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    REDIS_URL: str = ""
    FMP_API_KEY: str = ""
    ALPHA_VANTAGE_API_KEY: str = ""
    NEWS_API_KEY: str = ""
    POLYGON_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    BRAVE_SEARCH_API_KEY: str = ""

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings():
    return Settings()
