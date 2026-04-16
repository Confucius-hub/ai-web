import logging
from typing import AsyncIterator

import httpx

from app.ml_model.llm_interface import LLMInterface

logger = logging.getLogger(__name__)


class OpenRouterLLM(LLMInterface):
    """LLM-провайдер через OpenRouter API (OpenAI-совместимый)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        logger.info("OpenRouterLLM initialized with model=%s", model)

    @property
    def model_name(self) -> str:
        return self._model

    def _build_messages(self, prompt: str) -> list[dict[str, str]]:
        return [{"role": "user", "content": prompt}]

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 100,
    ) -> str:
        payload = {
            "model": self._model,
            "messages": self._build_messages(prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers,
                    json=payload,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "OpenRouter API error: %s %s",
                    exc.response.status_code,
                    exc.response.text[:200],
                )
                raise RuntimeError(
                    f"LLM provider returned {exc.response.status_code}"
                ) from exc
            except httpx.RequestError as exc:
                logger.error("OpenRouter connection error: %s", exc)
                raise RuntimeError("Failed to connect to LLM provider") from exc

        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 100,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self._model,
            "messages": self._build_messages(prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    headers=self._headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        import json

                        try:
                            parsed = json.loads(chunk)
                        except json.JSONDecodeError:
                            continue
                        delta = parsed["choices"][0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "OpenRouter stream error: %s %s",
                    exc.response.status_code,
                    exc.response.text[:200],
                )
                raise RuntimeError(
                    f"LLM provider returned {exc.response.status_code}"
                ) from exc
            except httpx.RequestError as exc:
                logger.error("OpenRouter stream connection error: %s", exc)
                raise RuntimeError("Failed to connect to LLM provider") from exc
