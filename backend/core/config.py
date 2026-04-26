from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout: int = 120

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    # Adzuna
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_country: str = "in"

    # Scraper
    max_jobs_per_source: int = 25

    # Cache
    cache_ttl_seconds: int = 3600
    max_cached_jobs: int = 500

    # CORS
    frontend_url: str = "http://localhost:5173"

    class Config:
        env_file = "backend/.env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()