"""Cross Encoder Reranking Agent (design §30).

Uses a sentence-transformers ``CrossEncoder`` (e.g. ``bge-reranker-large``) when
installed and enabled, to re-score the top retrieved items against the query and
keep the best few before they are sent to GPT-4o. When the cross-encoder is not
available it falls back to the hybrid ranking order already computed upstream.
"""

from __future__ import annotations

import functools
import logging

from rag.config import SETTINGS
from rag.models import RetrievedItem

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def _load_cross_encoder():  # pragma: no cover - heavy optional dependency
    from sentence_transformers import CrossEncoder

    logger.info("Loading cross-encoder reranker: %s", SETTINGS.cross_encoder_model)
    return CrossEncoder(SETTINGS.cross_encoder_model)


class CrossEncoderReranker:
    """Lazily-loaded cross-encoder reranker.

    The heavy ``bge-reranker-large`` HuggingFace model is downloaded/loaded only
    when reranking is enabled (``RAG_USE_CROSS_ENCODER=true``) AND ``rerank`` is
    actually called for the first time. When disabled, constructing this class
    and importing the search pipeline triggers no download and no model load.
    """

    def __init__(self) -> None:
        self._enabled = SETTINGS.use_cross_encoder
        self._model = None
        self._load_attempted = False

    def _ensure_model(self) -> None:
        """Load the model on first use; disable on failure (one attempt only)."""
        if self._model is not None or self._load_attempted:
            return
        self._load_attempted = True
        try:  # pragma: no cover - heavy optional dependency
            self._model = _load_cross_encoder()
        except Exception as exc:
            logger.info(
                "Cross-encoder unavailable (%s); using hybrid-rank order for reranking.",
                exc,
            )
            self._enabled = False

    def rerank(self, query: str, items: list[RetrievedItem], top_k: int) -> list[RetrievedItem]:
        if not items:
            return []
        if self._enabled:
            self._ensure_model()
        if not self._enabled or self._model is None:
            # Fall back to existing hybrid order.
            ordered = sorted(items, key=lambda it: it.final_score, reverse=True)
            for it in ordered:
                it.rerank_score = it.final_score
            return ordered[:top_k]

        pairs = [(query, it.payload.get("text", "")) for it in items]  # pragma: no cover
        scores = self._model.predict(pairs)  # pragma: no cover
        for it, score in zip(items, scores):  # pragma: no cover
            it.rerank_score = float(score)
        ordered = sorted(items, key=lambda it: it.rerank_score or 0.0, reverse=True)  # pragma: no cover
        return ordered[:top_k]  # pragma: no cover


# Single shared instance (probes for the cross-encoder model only once).
cross_encoder_reranker = CrossEncoderReranker()
