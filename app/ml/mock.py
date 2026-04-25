"""
# Изоляция ML-логики
MockLLM — тестовый режим без реальной модели. Возвращает эхо-ответ.
Используется, когда LLM_MODE=mock или когда нет API-ключа.
"""
from __future__ import annotations

import asyncio
import time

from app.ml.interface import GenerationResult, LLMInterface


class MockLLM(LLMInterface):
    model_name = "mock-echo"

    async def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
    ) -> GenerationResult:
        start = time.perf_counter()
        # имитируем inference latency ~200ms
        await asyncio.sleep(0.2)
        # Управление ресурсами: обрезаем длинный промпт до лимита
        trimmed = prompt[: max_new_tokens * 4]
        content = f"[mock reply] You said: {trimmed}"
        return GenerationResult(
            content=content,
            model=self.model_name,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            metadata={"mode": "mock"},
        )
