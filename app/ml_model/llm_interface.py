from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMInterface(ABC):
    """Единый интерфейс для всех LLM-провайдеров."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 100,
    ) -> str:
        ...

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 100,
    ) -> AsyncIterator[str]:
        ...
