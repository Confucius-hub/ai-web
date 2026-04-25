"""
# Логирование
Настроено структурное JSON-логирование (как в уроке — не print, а logging),
чтобы Docker/ELK-stack/Prometheus могли собирать логи.

Также содержит утилиту измерения времени этапов.
"""
from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from typing import Iterator

from pythonjsonlogger import jsonlogger


def setup_logging(level: str = "INFO") -> None:
    """Настраивает корневой логгер: JSON-формат, stdout."""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={"asctime": "ts", "levelname": "level"},
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Silence noisy libraries
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# Логирование времени всех этапов работы приложения
@contextmanager
def log_duration(logger: logging.Logger, stage: str, **extra) -> Iterator[None]:
    """
    Контекстный менеджер: логирует сколько времени заняла операция.
    Использование:
        with log_duration(log, "db.insert_user", user_id=42):
            await session.commit()
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "stage_done",
            extra={"stage": stage, "duration_ms": round(elapsed_ms, 2), **extra},
        )
