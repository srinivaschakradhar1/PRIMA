"""Configuration for the RAG pipeline.

All tunable parameters and external-service credentials live here. Values are
read from environment variables (a local ``.env`` file is loaded automatically
if ``python-dotenv`` is installed) so the pipeline can run against real OpenAI
services in production while falling back to fully-offline deterministic
implementations during local development / demos.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Load a local .env file if present (best-effort; never fatal).
try:  # pragma: no cover - trivial bootstrap
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:  # pragma: no cover
    pass


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
VECTORSTORE_DIR = _PROJECT_ROOT / "data" / "vectorstore"


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        return float(raw) if raw is not None else default
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


@dataclass(frozen=True)
class RagSettings:
    """Immutable snapshot of RAG configuration."""

    # --- OpenAI ---------------------------------------------------------
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
    embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")

    # --- Semantic merge agent -------------------------------------------
    merge_similarity_threshold: float = _get_float("RAG_MERGE_SIM_THRESHOLD", 0.75)
    merge_min_confidence: float = _get_float("RAG_MERGE_MIN_CONFIDENCE", 0.6)

    # --- Chunking (token budgets, per design doc) -----------------------
    parent_min_tokens: int = _get_int("RAG_PARENT_MIN_TOKENS", 1500)
    parent_max_tokens: int = _get_int("RAG_PARENT_MAX_TOKENS", 2500)
    child_min_tokens: int = _get_int("RAG_CHILD_MIN_TOKENS", 200)
    child_max_tokens: int = _get_int("RAG_CHILD_MAX_TOKENS", 500)

    # --- Search ---------------------------------------------------------
    retrieval_top_k: int = _get_int("RAG_RETRIEVAL_TOP_K", 20)
    rerank_top_k: int = _get_int("RAG_RERANK_TOP_K", 5)
    incident_top_k: int = _get_int("RAG_INCIDENT_TOP_K", 5)
    context_max_tokens: int = _get_int("RAG_CONTEXT_MAX_TOKENS", 3000)
    use_cross_encoder: bool = _get_bool("RAG_USE_CROSS_ENCODER", True)
    cross_encoder_model: str = os.getenv(
        "RAG_CROSS_ENCODER_MODEL", "BAAI/bge-reranker-large"
    )

    @property
    def openai_enabled(self) -> bool:
        return _is_real_openai_key(self.openai_api_key)


# Substrings that mark an obviously fake / placeholder API key. A real OpenAI
# key starts with ``sk-`` and never contains these, so this only ever disables
# the online path for clearly-unset credentials (e.g. a copied ``.env``).
_PLACEHOLDER_MARKERS = (
    "dummy", "placeholder", "your", "replace", "example", "xxxx", "<", "changeme",
)


def _is_real_openai_key(key: str | None) -> bool:
    if not key:
        return False
    value = key.strip()
    if not value.startswith("sk-") or len(value) < 20:
        return False
    lowered = value.lower()
    return not any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


SETTINGS = RagSettings()

if SETTINGS.openai_enabled:
    logger.info("RAG pipeline configured with OpenAI (chat=%s, embed=%s).",
                SETTINGS.chat_model, SETTINGS.embedding_model)
elif SETTINGS.openai_api_key:
    logger.error(
        "OPENAI_API_KEY looks like a placeholder/invalid value. The RAG pipeline "
        "has no offline fallback and will raise OpenAIUnavailableError on use. Set "
        "a real sk-... key to enable GPT-4o + text-embedding-3-large."
    )
else:
    logger.error(
        "OPENAI_API_KEY not set. The RAG pipeline has no offline fallback and will "
        "raise OpenAIUnavailableError on use."
    )
