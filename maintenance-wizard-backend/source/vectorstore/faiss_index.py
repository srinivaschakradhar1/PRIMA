"""FAISS vector store initialization and persistence.

Delegates to :mod:`rag.vectorstore`, which manages five separate, disk-persisted
indexes (manual, sop, failure_report, maintenance_log, spare_part). This hook is
called during application startup (per the documented "Initialize FAISS" step)
to ensure the vectorstore directory exists and the persisted indexes are loaded
into memory.
"""

from __future__ import annotations

import logging

from rag.config import VECTORSTORE_DIR
from rag.vectorstore import ALL_INDEX_NAMES, vector_store

logger = logging.getLogger(__name__)


def initialize_faiss_index() -> None:
    """Load (or create) the persisted per-document-type FAISS indexes."""
    VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)
    # Touch every index so persisted data is loaded eagerly at startup.
    stats = vector_store.stats()
    logger.info(
        "Vector store ready at %s. Indexes: %s",
        VECTORSTORE_DIR,
        ", ".join(f"{name}={stats.get(name, 0)}" for name in ALL_INDEX_NAMES),
    )
