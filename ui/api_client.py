"""
# Слабая связность
UI общается с бэкендом ТОЛЬКО через REST API.
Никаких прямых импортов из папки бэкенда.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_API = os.getenv("API_BASE_URL", "http://nginx/api")


class APIClient:
    def __init__(self, base_url: str = DEFAULT_API, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def health(self) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(self._url("/health"))
            r.raise_for_status()
            return r.json()

    # Users
    def create_user(self, name: str, email: str | None = None) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(self._url("/users"), json={"name": name, "email": email})
            r.raise_for_status()
            return r.json()

    def list_users(self) -> list[dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(self._url("/users"))
            r.raise_for_status()
            return r.json()

    # Sessions
    def create_session(self, user_id: int, title: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(
                self._url(f"/users/{user_id}/sessions"), json={"title": title}
            )
            r.raise_for_status()
            return r.json()

    def list_sessions(self, user_id: int) -> list[dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(self._url(f"/users/{user_id}/sessions"))
            r.raise_for_status()
            return r.json()

    def get_messages(self, user_id: int, session_id: int) -> list[dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(
                self._url(f"/users/{user_id}/sessions/{session_id}/messages")
            )
            r.raise_for_status()
            return r.json()

    # Chat
    def chat_sync(self, session_id: int, prompt: str, creativity: float,
                  max_new_tokens: int) -> dict[str, Any]:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                self._url("/chat"),
                json={
                    "session_id": session_id,
                    "prompt": prompt,
                    "creativity": creativity,
                    "max_new_tokens": max_new_tokens,
                },
            )
            r.raise_for_status()
            return r.json()

    def chat_async(self, session_id: int, prompt: str, creativity: float,
                   max_new_tokens: int) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(
                self._url("/chat/async"),
                json={
                    "session_id": session_id,
                    "prompt": prompt,
                    "creativity": creativity,
                    "max_new_tokens": max_new_tokens,
                },
            )
            r.raise_for_status()
            return r.json()

    def get_task(self, task_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(self._url(f"/tasks/{task_id}"))
            r.raise_for_status()
            return r.json()

    # Classification (own ONNX)
    def classify(self, text: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(self._url("/classify"), json={"text": text})
            r.raise_for_status()
            return r.json()
