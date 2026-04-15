import asyncio
import logging
import time

from app.ml_model.llm_interface import LLMInterface

logger = logging.getLogger(__name__)


class MockLLM(LLMInterface):
    _model_name = "MockLLM"

    def __init__(self) -> None:
        logger.info("[Weights are loading].")
        time.sleep(0.2)
        logger.info("[Weights are loaded].")
        self.semaphore = asyncio.Semaphore(2)

    @property
    def model_name(self) -> str:
        return self._model_name

    @staticmethod
    def _build_response_tokens(
        prompt: str, temperature: float, max_tokens: int
    ) -> list[str]:
        prompt_tokens = prompt.split() or ["<empty>"]
        generated_tokens = [
            f"{MockLLM._model_name}[temp={temperature:.2f}]",
            "=>",
            *prompt_tokens,
        ]
        return generated_tokens[: max_tokens or 1]

    async def generate(self, prompt: str, temperature: float, max_tokens: int) -> str:
        tokens = self._build_response_tokens(prompt, temperature, max_tokens)

        async with self.semaphore:
            logger.info(
                f"Generating response on `prompt`: {prompt[:10]}... with `temperature`:{temperature}"
            )
            logger.info(f"Slots available: {2 - self.semaphore._value}/2.")
            await asyncio.sleep(0.2)
            return " ".join(tokens)

    async def generate_stream(self, prompt: str, temperature: float, max_tokens: int):
        tokens = self._build_response_tokens(prompt, temperature, max_tokens)

        async with self.semaphore:
            await asyncio.sleep(0.1)
            for token in tokens:
                await asyncio.sleep(0.05)
                yield f"{token} "
