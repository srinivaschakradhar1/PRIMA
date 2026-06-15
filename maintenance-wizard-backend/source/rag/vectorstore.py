"""Per-document-type vector indexes (design §20).

Five separate, disk-persisted indexes are maintained (manual, sop,
failure_report, maintenance_log, spare_part) rather than a single index. Each
index stores L2-normalised vectors plus a parallel list of entry payloads
(chunk / incident / maintenance-log metadata + text).

FAISS (``IndexFlatIP``) is used for search when installed; otherwise a numpy
brute-force dot product is used. Both back ends persist identically (a ``.npy``
matrix + ``.json`` sidecar) so switching back ends never invalidates data.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

import numpy as np

from rag.config import VECTORSTORE_DIR
from rag.lexical import BM25, tokenize
from rag.models import RetrievedItem

logger = logging.getLogger(__name__)

# Reciprocal Rank Fusion constant (standard value); dampens the influence of any
# single ranker's absolute scores when fusing dense + lexical result lists.
_RRF_K = 60

# DocumentType -> index name.
DOCTYPE_TO_INDEX = {
    "MANUAL": "manual_index",
    "SOP": "sop_index",
    "FAILURE_REPORT": "failure_report_index",
    "MAINTENANCE_LOG": "maintenance_log_index",
    "SPARE_PART": "spare_part_index",
}
ALL_INDEX_NAMES = list(DOCTYPE_TO_INDEX.values())

try:  # pragma: no cover - optional dependency
    import faiss  # type: ignore

    _HAS_FAISS = True
except Exception:  # pragma: no cover
    faiss = None  # type: ignore
    _HAS_FAISS = False


def index_name_for_doctype(document_type: str | None) -> str:
    return DOCTYPE_TO_INDEX.get((document_type or "").upper(), "manual_index")


class VectorIndex:
    """A single named vector index with disk persistence."""

    def __init__(self, name: str, directory: Path) -> None:
        self.name = name
        self._vectors_path = directory / f"{name}.npy"
        self._meta_path = directory / f"{name}.json"
        self._vectors: np.ndarray | None = None
        self._entries: list[dict[str, Any]] = []
        self._dim: int | None = None
        self._faiss = None
        self._faiss_dirty = True
        self._bm25: BM25 | None = None
        self._bm25_dirty = True
        self._load()

    # -- persistence -----------------------------------------------------
    def _load(self) -> None:
        if self._meta_path.exists() and self._vectors_path.exists():
            try:
                meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
                self._entries = meta.get("entries", [])
                self._dim = meta.get("dim")
                self._vectors = np.load(self._vectors_path).astype(np.float32)
                logger.info("Loaded index '%s' (%d entries).", self.name, len(self._entries))
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to load index '%s' (%s); starting empty.", self.name, exc)
                self._vectors, self._entries, self._dim = None, [], None

    def _persist(self) -> None:
        self._vectors_path.parent.mkdir(parents=True, exist_ok=True)
        vectors = self._vectors if self._vectors is not None else np.zeros((0, self._dim or 1), dtype=np.float32)
        np.save(self._vectors_path, vectors)
        self._meta_path.write_text(
            json.dumps({"dim": self._dim, "entries": self._entries}),
            encoding="utf-8",
        )

    # -- mutation --------------------------------------------------------
    def add(self, vectors: np.ndarray, entries: list[dict[str, Any]]) -> None:
        if len(entries) == 0:
            return
        vectors = vectors.astype(np.float32)
        if self._dim is None:
            self._dim = vectors.shape[1]
        if vectors.shape[1] != self._dim:
            raise ValueError(
                f"Embedding dim {vectors.shape[1]} != index '{self.name}' dim {self._dim}. "
                "Delete data/vectorstore to rebuild after changing embedding model."
            )
        if self._vectors is None or self._vectors.size == 0:
            self._vectors = vectors
        else:
            self._vectors = np.vstack([self._vectors, vectors])
        self._entries.extend(entries)
        self._faiss_dirty = True
        self._bm25_dirty = True
        self._persist()

    def remove_document(self, document_id: str) -> int:
        if not self._entries:
            return 0
        keep = [i for i, e in enumerate(self._entries) if e.get("document_id") != document_id]
        removed = len(self._entries) - len(keep)
        if removed == 0:
            return 0
        self._entries = [self._entries[i] for i in keep]
        self._vectors = self._vectors[keep] if self._vectors is not None and keep else None
        if not keep:
            self._vectors = np.zeros((0, self._dim or 1), dtype=np.float32)
        self._faiss_dirty = True
        self._bm25_dirty = True
        self._persist()
        return removed

    # -- search ----------------------------------------------------------
    def search(self, query: np.ndarray, top_k: int) -> list[tuple[float, dict[str, Any]]]:
        if self._vectors is None or self._vectors.shape[0] == 0:
            return []
        q = query.astype(np.float32).reshape(1, -1)
        norm = float(np.linalg.norm(q))
        if norm:
            q = q / norm
        k = min(top_k, self._vectors.shape[0])
        if _HAS_FAISS:  # pragma: no cover - optional dependency
            scores, idxs = self._search_faiss(q, k)
        else:
            sims = (self._vectors @ q.T).ravel()
            idxs = np.argsort(-sims)[:k]
            scores = sims[idxs]
        return [(float(scores[i]), self._entries[int(idxs[i])]) for i in range(len(idxs))]

    def _search_faiss(self, q: np.ndarray, k: int):  # pragma: no cover
        if self._faiss is None or self._faiss_dirty:
            index = faiss.IndexFlatIP(self._dim)
            index.add(self._vectors)
            self._faiss = index
            self._faiss_dirty = False
        scores, idxs = self._faiss.search(q, k)
        return scores[0], idxs[0]

    # -- hybrid (dense + BM25 lexical) search ----------------------------
    def _ensure_bm25(self) -> None:
        """(Re)build the BM25 index from current entry texts on first use/change."""
        if self._bm25 is not None and not self._bm25_dirty:
            return
        corpus = [tokenize(e.get("text", "")) for e in self._entries]
        self._bm25 = BM25(corpus)
        self._bm25_dirty = False

    def hybrid_search(
        self,
        query: np.ndarray,
        query_text: str,
        top_k: int,
        *,
        equipment_id: str | None = None,
    ) -> list[tuple[float, float, dict[str, Any]]]:
        """Fuse dense (cosine) and lexical (BM25) retrieval via Reciprocal Rank
        Fusion.

        Returns ``(semantic_score, lexical_score, entry)`` tuples, both scores in
        ``[0, 1]``. The union of each ranker's top-``top_k`` is considered so an
        exact code match the dense ranker missed (and vice-versa) still surfaces;
        the fused order decides which ``top_k`` are returned.

        When ``equipment_id`` is given, the candidate set is restricted to the
        rows whose payload ``equipment_id`` matches it *before* ranking, so both
        the dense and lexical rankers only ever see (and therefore only ever
        return) embeddings belonging to that equipment. Returns an empty list if
        the index holds nothing for the equipment.
        """
        if self._vectors is None or self._vectors.shape[0] == 0:
            return []
        n = self._vectors.shape[0]

        # Restrict candidates to the requested equipment so retrieval never
        # crosses equipment boundaries.
        allowed_set: set[int] | None = None
        if equipment_id is not None:
            allowed = [
                i for i, e in enumerate(self._entries)
                if e.get("equipment_id") == equipment_id
            ]
            if not allowed:
                return []
            allowed_set = set(allowed)

        k = min(top_k, len(allowed_set) if allowed_set is not None else n)

        # Dense cosine over all rows (vectors and query are L2-normalised, so the
        # dot product is cosine). Computed directly in numpy rather than via FAISS
        # so we have a score for every row available to the fusion step.
        q = query.astype(np.float32).reshape(-1)
        norm = float(np.linalg.norm(q))
        if norm:
            q = q / norm
        sims = (self._vectors @ q).astype(np.float32)
        if allowed_set is not None:
            allowed_arr = np.asarray(sorted(allowed_set))
            local_order = np.argsort(-sims[allowed_arr])[: max(k, top_k)]
            dense_order = [int(allowed_arr[i]) for i in local_order]
        else:
            dense_order = list(np.argsort(-sims)[: max(k, top_k)])
        dense_rank = {int(idx): r for r, idx in enumerate(dense_order)}

        # Lexical BM25.
        lex_rank: dict[int, int] = {}
        lex = [0.0] * n
        lex_max = 0.0
        if query_text and query_text.strip():
            self._ensure_bm25()
            lex = self._bm25.scores(query_text) if self._bm25 else lex
            if allowed_set is not None:
                # Drop lexical scores for out-of-scope rows so they cannot enter
                # the fused candidate set.
                lex = [s if i in allowed_set else 0.0 for i, s in enumerate(lex)]
            lex_max = max(lex) if lex else 0.0
            if lex_max > 0.0:
                lex_order = [i for i in np.argsort(-np.asarray(lex))[: max(k, top_k)] if lex[int(i)] > 0.0]
                lex_rank = {int(idx): r for r, idx in enumerate(lex_order)}

        # Reciprocal Rank Fusion over the union of both candidate sets.
        candidates = set(dense_rank) | set(lex_rank)
        fused: list[tuple[int, float]] = []
        for idx in candidates:
            score = 0.0
            if idx in dense_rank:
                score += 1.0 / (_RRF_K + dense_rank[idx])
            if idx in lex_rank:
                score += 1.0 / (_RRF_K + lex_rank[idx])
            fused.append((idx, score))
        fused.sort(key=lambda pair: pair[1], reverse=True)

        out: list[tuple[float, float, dict[str, Any]]] = []
        for idx, _ in fused[:top_k]:
            lex_norm = (lex[idx] / lex_max) if lex_max > 0.0 else 0.0
            out.append((float(sims[idx]), float(lex_norm), self._entries[idx]))
        return out

    def ref_ids_for_document(self, document_id: str) -> list[str]:
        """Chunk ref_ids from this index belonging to ``document_id``."""
        return [
            e.get("ref_id")
            for e in self._entries
            if e.get("document_id") == document_id
            and e.get("kind") == "chunk"
            and e.get("ref_id")
        ]

    @property
    def size(self) -> int:
        return len(self._entries)


class VectorStoreManager:
    """Owns all named indexes and routes add/search/remove operations."""

    def __init__(self, directory: Path = VECTORSTORE_DIR) -> None:
        self._directory = directory
        self._indexes: dict[str, VectorIndex] = {}
        self._lock = threading.RLock()
        directory.mkdir(parents=True, exist_ok=True)

    def _get(self, name: str) -> VectorIndex:
        if name not in self._indexes:
            self._indexes[name] = VectorIndex(name, self._directory)
        return self._indexes[name]

    def add(self, index_name: str, vectors: np.ndarray, entries: list[dict[str, Any]]) -> None:
        with self._lock:
            self._get(index_name).add(vectors, entries)

    def remove_document(self, document_id: str) -> int:
        total = 0
        with self._lock:
            for name in ALL_INDEX_NAMES:
                total += self._get(name).remove_document(document_id)
        logger.info("Removed %d vector entries for document %s.", total, document_id)
        return total

    def search(
        self, index_names: list[str], query: np.ndarray, top_k: int
    ) -> list[RetrievedItem]:
        results: list[RetrievedItem] = []
        with self._lock:
            for name in index_names:
                for score, entry in self._get(name).search(query, top_k):
                    results.append(
                        RetrievedItem(
                            kind=entry.get("kind", "chunk"),
                            ref_id=entry.get("ref_id", ""),
                            index_name=name,
                            semantic_score=score,
                            payload=entry,
                        )
                    )
        return results

    def hybrid_search(
        self,
        index_names: list[str],
        query: np.ndarray,
        query_text: str,
        top_k: int,
        *,
        equipment_id: str | None = None,
    ) -> list[RetrievedItem]:
        """Dense + BM25 lexical retrieval across the named indexes (RRF-fused).

        Mirrors :meth:`search` but carries a ``lexical_score`` so the downstream
        hybrid ranker can reward exact code / part-number / fault-code matches.

        When ``equipment_id`` is given, retrieval is restricted to embeddings
        belonging to that equipment (see :meth:`VectorIndex.hybrid_search`).
        """
        results: list[RetrievedItem] = []
        with self._lock:
            for name in index_names:
                for sem, lex, entry in self._get(name).hybrid_search(
                    query, query_text, top_k, equipment_id=equipment_id
                ):
                    results.append(
                        RetrievedItem(
                            kind=entry.get("kind", "chunk"),
                            ref_id=entry.get("ref_id", ""),
                            index_name=name,
                            semantic_score=sem,
                            lexical_score=lex,
                            payload=entry,
                        )
                    )
        return results

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {name: self._get(name).size for name in ALL_INDEX_NAMES}

    def index_map_for_document(self, document_id: str) -> dict[str, str]:
        """Map each indexed chunk ref_id of a document to its index name."""
        out: dict[str, str] = {}
        with self._lock:
            for name in ALL_INDEX_NAMES:
                for ref_id in self._get(name).ref_ids_for_document(document_id):
                    out[ref_id] = name
        return out


# Single shared manager (indexes lazy-load from disk on first access).
vector_store = VectorStoreManager()
