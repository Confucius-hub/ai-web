import json
import logging
import time
from contextlib import asynccontextmanager
from logging.config import dictConfig
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.ml_model.llm_interface import LLMInterface
from app.ml_model.ml_model import MockLLM
from app.routers.router import router

settings = get_settings()

with (Path(__file__).resolve().parent.parent / "log_config.json").open(
    encoding="utf-8"
) as log_config_file:
    dictConfig(json.load(log_config_file))

logger = logging.getLogger(__name__)

ml_model_state: dict[str, Any] = {}


def create_llm() -> LLMInterface:
    """Создаёт LLM в зависимости от LLM_MODE в конфигурации."""
    if settings.LLM_MODE == "real":
        if not settings.LLM_API_KEY:
            raise ValueError("LLM_API_KEY is required when LLM_MODE=real")
        from app.ml_model.openrouter_llm import OpenRouterLLM

        logger.info(
            "Starting in REAL mode: provider=OpenRouter, model=%s",
            settings.LLM_MODEL,
        )
        return OpenRouterLLM(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
        )
    else:
        logger.info("Starting in MOCK mode: using MockLLM")
        return MockLLM()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ml_model_state["ml_model"] = create_llm()
    logger.info("Server is ready to accept connections.")
    yield
    ml_model_state.clear()
    logger.info("Memory is successfully freed.")


app = FastAPI(title=settings.APP_TITLE, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


class ContextLengthExceeded(Exception):
    def __init__(self, limit: int):
        self.limit = limit


@app.exception_handler(ContextLengthExceeded)
async def context_length_handler(request: Request, exc: ContextLengthExceeded):
    logger.error("LLM context overflow")

    return JSONResponse(
        status_code=400,
        content={"error": f"Input message is greater than {exc.limit} symbols."},
    )


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    started_at = time.perf_counter()
    response = await call_next(request)
    process_time_ms = (time.perf_counter() - started_at) * 1000
    response.headers["X-Process-Time"] = f"{process_time_ms:.1f}ms"
    return response
