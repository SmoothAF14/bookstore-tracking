"""
core/llm.py — Orchestration LLM client provider.

An OpenAI-compatible client pointed at OpenRouter (LLM_BASE_URL), used by the
orchestrator to decide the next tracking checkpoint + order-status transition.
"""
from functools import lru_cache

from app.core.config import settings


@lru_cache
def get_llm_client():
    """Return a configured OpenAI-compatible client (OpenRouter).

    Lazily imported so the service can boot (e.g. for /health) even when the
    SDK or API key is not yet configured.
    """
    if not settings.LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY is not set — configure your OpenRouter API key in .env "
            "before using the tracking orchestrator."
        )

    from openai import OpenAI

    return OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
