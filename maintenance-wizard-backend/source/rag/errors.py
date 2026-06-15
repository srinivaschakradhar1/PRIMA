"""Shared RAG error types."""

from __future__ import annotations


class OpenAIUnavailableError(RuntimeError):
    """Raised when an OpenAI-backed step cannot run.

    The pipeline has no offline fallback by design: embeddings, classification,
    extraction and answer generation all require OpenAI. Rather than silently
    degrading to low-quality heuristics, every OpenAI-backed step raises this so
    the failure is loud and surfaces to the caller (and the API as a 503).
    """
