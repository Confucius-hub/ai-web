"""
# Изоляция ML-логики
Factory — по значению LLM_MODE возвращает нужную реализацию.
"""
from __future__ import annotations

import logging

from app.core.config import Settings
from app.ml.interface import LLMInterface
from app.ml.mock import MockLLM
from app.ml.openrouter import OpenRouterLLM

log = logging.getLogger(__name__)


def build_llm(settings: Settings) -> LLMInterface:
    if settings.llm_mode == "real":
        if not settings.llm_api_key or settings.llm_api_key.startswith("replace_"):
            log.warning("llm_api_key_missing_fallback_to_mock")
            return MockLLM()
        return OpenRouterLLM(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return MockLLM()
