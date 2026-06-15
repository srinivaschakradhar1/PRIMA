"""LLM client wrapper around OpenAI GPT-4o.

Exposes two async helpers:

* :meth:`LLMClient.complete_json` - returns a parsed JSON object (uses OpenAI
  JSON mode).
* :meth:`LLMClient.complete_text` - returns free-form text (used for the final
  answer generation).

There is **no offline fallback**. When OpenAI is not configured or a call fails,
both helpers raise :class:`~rag.errors.OpenAIUnavailableError` so the failure is
loud and propagates to the caller instead of silently degrading to heuristics.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from rag.config import SETTINGS
from rag.errors import OpenAIUnavailableError

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self) -> None:
        self._client = None
        self._init_error: str | None = None
        if not SETTINGS.openai_enabled:
            self._init_error = (
                "OPENAI_API_KEY is not set to a valid sk-... key; the RAG pipeline "
                "requires OpenAI and has no offline fallback."
            )
            return
        try:  # pragma: no cover - optional dependency
            from openai import OpenAI

            self._client = OpenAI(api_key=SETTINGS.openai_api_key)
        except Exception as exc:  # pragma: no cover
            self._init_error = f"Failed to initialise OpenAI client: {exc}"
            logger.error(self._init_error)

    @property
    def available(self) -> bool:
        return self._client is not None

    def _require_client(self):
        if self._client is None:
            raise OpenAIUnavailableError(
                self._init_error or "OpenAI client is not available."
            )
        return self._client

    def verify_connectivity(self) -> None:
        """Make a cheap authenticated call; raise if OpenAI is unreachable."""
        client = self._require_client()
        try:  # pragma: no cover - network
            client.models.list()
        except Exception as exc:
            raise OpenAIUnavailableError(f"OpenAI connectivity check failed: {exc}") from exc

    async def complete_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 1500,
    ) -> dict[str, Any]:
        """Return a parsed JSON object. Raises ``OpenAIUnavailableError`` on failure."""
        self._require_client()
        try:
            return await asyncio.to_thread(
                self._call_json, system, user, temperature, max_tokens
            )
        except Exception as exc:  # pragma: no cover - network/runtime
            raise OpenAIUnavailableError(f"GPT JSON completion failed: {exc}") from exc

    async def complete_text(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        """Return free-form text. Raises ``OpenAIUnavailableError`` on failure."""
        self._require_client()
        try:
            return await asyncio.to_thread(
                self._call_text, system, user, temperature, max_tokens
            )
        except Exception as exc:  # pragma: no cover
            raise OpenAIUnavailableError(f"GPT text completion failed: {exc}") from exc

    # -- implementations -------------------------------------------------
    def _call_json(  # pragma: no cover - requires network
        self, system: str, user: str, temperature: float, max_tokens: int
    ) -> dict[str, Any]:
        resp = self._client.chat.completions.create(
            model=SETTINGS.chat_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)

    def _call_text(  # pragma: no cover - requires network
        self, system: str, user: str, temperature: float, max_tokens: int
    ) -> str:
        resp = self._client.chat.completions.create(
            model=SETTINGS.chat_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""


llm_client = LLMClient()
