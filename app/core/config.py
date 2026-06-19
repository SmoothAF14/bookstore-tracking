"""
core/config.py — Application settings via pydantic-settings.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV:   str = 'development'
    APP_DEBUG: bool = True
    PORT:      int = 8003

    CORS_ORIGINS:         str = 'http://localhost:3000'
    DJANGO_API_URL:       str = 'http://localhost:8000'
    DELIVERY_SERVICE_URL: str = 'http://localhost:8004'

    # ------------------------------------------------------------------
    # Redis / Celery — broker + result backend + tracking state store.
    #
    # On Render we provision a single managed Redis instance. Depending on how
    # it's wired, the connection string may arrive as REDIS_URL (Render's
    # default key name) OR as CELERY_BROKER_URL / CELERY_RESULT_BACKEND. We
    # accept any of them and fall back to localhost only for local dev, so the
    # deployed service never silently points at localhost.
    # ------------------------------------------------------------------
    REDIS_URL:             str = ''
    CELERY_BROKER_URL:     str = ''
    CELERY_RESULT_BACKEND: str = ''

    @property
    def celery_broker_url(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL or 'redis://localhost:6379/0'

    @property
    def celery_result_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL or 'redis://localhost:6379/1'

    @property
    def redis_url(self) -> str:
        """Connection string for the tracking state store (shares managed Redis)."""
        return (
            self.REDIS_URL
            or self.CELERY_RESULT_BACKEND
            or self.CELERY_BROKER_URL
            or 'redis://localhost:6379/0'
        )

    # ------------------------------------------------------------------
    # LLM provider (orchestration loop) — OpenAI-compatible API (OpenRouter).
    # ------------------------------------------------------------------
    LLM_API_KEY:    str = ''
    LLM_BASE_URL:   str = 'https://openrouter.ai/api/v1'
    LLM_MODEL:      str = 'deepseek/deepseek-v3.2'
    LLM_MAX_TOKENS: int = 1024

    # ------------------------------------------------------------------
    # Google Maps — MOCK DATA ONLY (no real billing/calls by default).
    # ------------------------------------------------------------------
    GOOGLE_MAPS_API_KEY:  str = ''
    GOOGLE_MAPS_USE_MOCK: bool = True

    # ------------------------------------------------------------------
    # Auth — validates JWT access tokens issued by the Django backend.
    # JWT_SECRET MUST equal the Django backend's SECRET_KEY (HS256).
    # ------------------------------------------------------------------
    JWT_SECRET:        str = ''
    JWT_ALGORITHM:     str = 'HS256'
    JWT_USER_ID_CLAIM: str = 'user_id'
    REQUIRE_AUTH:      bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(',') if o.strip()]

    class Config:
        env_file = '.env'


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
