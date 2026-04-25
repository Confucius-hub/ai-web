"""
# Изоляция ML-логики
Абстрактный интерфейс LLM — API не знает, как устроен провайдер.
Роуты вызывают `.generate()` и получают GenerationResult.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class GenerationResult:
    content: str
    model: str
    duration_ms: float
    metadata: dict


class LLMInterface(ABC):
    """Единый контракт для всех LLM-провайдеров (Mock / OpenRouter / ...)."""

    model_name: str = "unknown"

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """Синхронная (awaitable) генерация одного ответа."""

    async def healthcheck(self) -> bool:
        """По умолчанию считаем готовым. Переопределяется при необходимости."""
        return True
