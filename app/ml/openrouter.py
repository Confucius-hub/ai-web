"""
# Изоляция ML-логики
OpenRouterLLM — работа с реальной моделью через OpenRouter (OpenAI-совместимый API).
Ошибки провайдера (таймаут, 5xx, невалидный ключ) конвертируются в LLMError
и обрабатываются в общем error handler (возвращается 503).

# Управление ресурсами
max_new_tokens ограничивает длину ответа (защита от дорогих запросов).
"""
from __future__ import annotations

import logging
import time

import httpx

from app.core.errors import LLMError
from app.ml.interface import GenerationResult, LLMInterface

log = logging.getLogger(__name__)


class OpenRouterLLM(LLMInterface):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: int = 30,
    ) -> None:
        if not api_key:
            raise LLMError("LLM_API_KEY is not configured")
        self.model_name = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # OpenRouter рекомендует передавать эти заголовки:
            "HTTP-Referer": "https://github.com/Confucius-hub/ai-web",
            "X-Title": "ai-web",
        }

    async def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
    ) -> GenerationResult:
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            # Управление ресурсами
            "max_tokens": max_new_tokens,
            "temperature": temperature,
        }
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, headers=self._headers, json=payload)
        except httpx.TimeoutException as e:
            log.warning("llm_timeout", extra={"model": self.model_name})
            raise LLMError("LLM provider timeout") from e
        except httpx.HTTPError as e:
            log.warning("llm_network_error", extra={"error": str(e)})
            raise LLMError("LLM provider network error") from e

        if resp.status_code >= 500:
            raise LLMError(f"LLM provider error {resp.status_code}")
        if resp.status_code == 401:
            raise LLMError("LLM provider: invalid API key")
        if resp.status_code >= 400:
            raise LLMError(
                f"LLM provider bad request ({resp.status_code}): {resp.text[:200]}"
            )

        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMError("LLM provider returned unexpected payload") from e

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        return GenerationResult(
            content=content,
            model=self.model_name,
            duration_ms=duration_ms,
            metadata={
                "mode": "real",
                "provider": "openrouter",
                "usage": data.get("usage", {}),
            },
        )

    async def healthcheck(self) -> bool:
        # Лёгкая проверка — не дёргаем платный endpoint, просто HEAD на base_url
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self._base_url}/models", headers=self._headers)
            return r.status_code < 500
        except httpx.HTTPError:
            return False
