"""Embedding generation (OpenAI ``text-embedding-3-large``).

There is **no offline fallback**. When OpenAI is not configured or an embedding
call fails, :meth:`EmbeddingClient.embed` raises
:class:`~rag.errors.OpenAIUnavailableError`. A hashed bag-of-words fallback would
silently turn semantic retrieval into lexical matching, which is the exact
"silent danger" this pipeline now refuses to ship.
"""

from __future__ import annotations

import asyncio
import logging

import numpy as np

from rag.config import SETTINGS
from rag.errors import OpenAIUnavailableError

logger = logging.getLogger(__name__)

# text-embedding-3-large is 3072-dimensional.
_EMBED_DIM = 3072


class EmbeddingClient:
    """Embeds text into dense vectors using OpenAI."""

    def __init__(self) -> None:
        self._client = None
        self._init_error: str | None = None
        self._dim = _EMBED_DIM
        if not SETTINGS.openai_enabled:
            self._init_error = (
                "OPENAI_API_KEY is not set to a valid sk-... key; embeddings require "
                "OpenAI and have no offline fallback."
            )
            return
        try:  # pragma: no cover - optional dependency
            from openai import OpenAI

            self._client = OpenAI(api_key=SETTINGS.openai_api_key)
        except Exception as exc:  # pragma: no cover
            self._init_error = f"Failed to initialise OpenAI embedding client: {exc}"
            logger.error(self._init_error)

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def is_openai(self) -> bool:
        return self._client is not None

    def _require_client(self):
        if self._client is None:
            raise OpenAIUnavailableError(
                self._init_error or "OpenAI embedding client is not available."
            )
        return self._client

    def verify_connectivity(self) -> None:
        """Make a cheap authenticated call; raise if OpenAI is unreachable."""
        client = self._require_client()
        try:  # pragma: no cover - network
            client.models.list()
        except Exception as exc:
            raise OpenAIUnavailableError(
                f"OpenAI embedding connectivity check failed: {exc}"
            ) from exc

    # -- public API ------------------------------------------------------
    async def embed(self, texts: list[str]) -> np.ndarray:
        """Embed a batch of texts. Returns an ``(n, dim)`` float32 array.

        Raises :class:`OpenAIUnavailableError` if OpenAI is unavailable / fails.
        """
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        self._require_client()
        try:
            return await asyncio.to_thread(self._embed_openai, texts)
        except OpenAIUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network/runtime
            raise OpenAIUnavailableError(f"OpenAI embedding call failed: {exc}") from exc

    async def embed_one(self, text: str) -> np.ndarray:
        vecs = await self.embed([text])
        return vecs[0]

    # -- implementation --------------------------------------------------
    def _embed_openai(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        # OpenAI rejects empty strings; substitute a single space.
        cleaned = [t if t.strip() else " " for t in texts]
        resp = self._client.embeddings.create(model=SETTINGS.embedding_model, input=cleaned)
        vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)
        return _l2_normalize(vecs)


def _l2_normalize(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (vecs / norms).astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors (assumed finite)."""
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# Single shared instance (cheap to construct, holds the OpenAI client).
embedding_client = EmbeddingClient()
