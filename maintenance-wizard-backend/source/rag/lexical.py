"""Dependency-free BM25 lexical retrieval.

Dense embeddings (``text-embedding-3-large``) capture meaning well but
systematically under-weight *exact* alphanumeric tokens — and those tokens are
exactly what a steel-plant maintenance query hinges on:

* equipment codes      ``BF-101``, ``RM-204``
* fault / alarm codes  ``E-401``, ``ALM-23``
* spare-part numbers   ``6312-2RS``, ``SKF-22220``
* measurement specs    ``6.6kV``, ``1450rpm``

This module provides a small, well-known BM25 (Okapi) scorer plus a tokenizer
that *preserves* hyphenated / slashed code tokens (``BF-101`` stays one token
instead of becoming ``bf`` + ``101``). It is fused with dense retrieval via
Reciprocal Rank Fusion in :mod:`rag.vectorstore`, turning the previously
dense-only "hybrid ranking" into genuine dense+sparse hybrid search.

No third-party dependency: BM25 here is ~40 lines and runs over the per-index
chunk corpus already held in memory.
"""

from __future__ import annotations

import math
import re

# Keep code-like tokens intact: a run of letters/digits, optionally joined by
# '-' or '/' to further letter/digit runs (BF-101, 6312-2rs, p/n, 6.6kv stays
# as 6 + 6kv — periods are treated as separators, which is the desired split
# for sentence punctuation while ".5" style decimals are rare in codes).
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-/][a-z0-9]+)*")

# A compact English + boilerplate stop list. Deliberately small: dropping too
# much hurts recall on short maintenance phrases.
_STOPWORDS = frozenset(
    """a an and are as at be by for from has have in into is it its of on or
    that the their then there these this to was were what when where which
    who will with you your""".split()
)


def tokenize(text: str) -> list[str]:
    """Lower-case, code-preserving tokenizer used for both corpus and queries."""
    if not text:
        return []
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


class BM25:
    """Okapi BM25 over a fixed corpus of pre-tokenised documents.

    Built once per index snapshot and rebuilt only when the index changes. Uses
    an inverted index (postings) so scoring touches only documents that contain
    a query term, keeping it fast as corpora grow.
    """

    __slots__ = ("k1", "b", "n", "_doc_len", "_avgdl", "_idf", "_postings")

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.n = len(corpus)
        self._doc_len = [len(doc) for doc in corpus]
        self._avgdl = (sum(self._doc_len) / self.n) if self.n else 0.0

        # term -> list of (doc_index, term_frequency)
        postings: dict[str, list[tuple[int, int]]] = {}
        df: dict[str, int] = {}
        for i, doc in enumerate(corpus):
            freqs: dict[str, int] = {}
            for term in doc:
                freqs[term] = freqs.get(term, 0) + 1
            for term, freq in freqs.items():
                postings.setdefault(term, []).append((i, freq))
                df[term] = df.get(term, 0) + 1
        self._postings = postings
        # BM25 idf with the standard +0.5 smoothing (always positive via the 1+ ).
        self._idf = {
            term: math.log(1 + (self.n - n_t + 0.5) / (n_t + 0.5))
            for term, n_t in df.items()
        }

    def scores(self, query: str) -> list[float]:
        """Return a BM25 score per corpus document for ``query`` (len == n)."""
        out = [0.0] * self.n
        if self.n == 0 or self._avgdl == 0.0:
            return out
        seen: set[str] = set()
        for term in tokenize(query):
            if term in seen:
                continue
            seen.add(term)
            idf = self._idf.get(term)
            if idf is None:
                continue
            postings = self._postings.get(term)
            if not postings:
                continue
            for doc_idx, freq in postings:
                denom = freq + self.k1 * (
                    1 - self.b + self.b * self._doc_len[doc_idx] / self._avgdl
                )
                out[doc_idx] += idf * (freq * (self.k1 + 1)) / denom
        return out
