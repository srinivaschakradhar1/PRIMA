# RAG Architecture — Maintenance Wizard Backend

This document describes how the Retrieval-Augmented Generation (RAG) ingestion
and retrieval pipelines are implemented, and the reasoning behind each design
choice. Code references point at the relevant modules under `src/rag/`.

---

## 0. Foundational design decisions

Two choices shape everything below:

**Hard dependency on OpenAI, no silent fallback.** `embeddings.py`, `llm.py`,
and `config.py` all refuse to degrade. If `OPENAI_API_KEY` isn't a real `sk-...`
key, the app aborts at startup (connectivity probe) and every ingest/search
returns HTTP 503.

- *Why:* A hashed bag-of-words embedding fallback would silently convert
  semantic retrieval into lexical matching — answers would still come back, just
  quietly wrong. For a maintenance system where a bad answer can mean a
  misdiagnosed failure, the team chose loud failure over silent degradation
  (`rag/embeddings.py`).

**Stack auto-detects optional native deps and degrades only on *infrastructure*,
not *intelligence*.** FAISS, PyMuPDF, tiktoken, sentence-transformers, and
python-docx are each probed at import and have graceful fallbacks (numpy
brute-force search, raw-text parsing, char-count token estimation, hybrid-rank
ordering).

- *Why:* These affect the speed/quality of mechanics, not the correctness of
  meaning. A demo box without FAISS still works; one without embeddings does
  not. The line is drawn deliberately.

---

## 1. Ingestion pipeline

Orchestrated by `IngestionPipeline.ingest()` (`rag/ingestion.py`), invoked by
`KnowledgeService` on document upload/replace. Stages:

```
parse → section embeddings → semantic merge → concept extraction →
relationship extraction → chunk boundaries → embed children →
content-routed FAISS index + SQLite → special structured extraction
```

### Step 1 — Layout-aware parsing (`parsing.py`)

PDFs are parsed with **PyMuPDF in `dict` mode**, exposing font size, bold flags,
and bounding boxes. From that structural signal the parser:

- detects headings by **typography** (size ≥ body+1, bold, all-caps) rather than
  fragile string heuristics;
- strips **repeated headers/footers** (a line recurring in the top/bottom 14%
  margin on ≥30% of pages);
- **reassembles** headings the PDF wrapped across multiple lines;
- keeps **tables intact** as pipe-delimited blocks.

Output is a canonical `full_text` string plus offset-anchored `DocumentSection`s.

- *Why typography over string rules:* Earlier string heuristics promoted body
  sentences and clause numbers to headings. Font signal is far more reliable in
  technical standards/spec PDFs.
- *Why offsets are the source of truth:* Every later stage slices text from
  `full_text[start:end]` and **never regenerates it**. This guarantees chunks
  are verbatim source text — critical for citation integrity and for never
  hallucinating content during chunking.
- *Why strip boilerplate before sectioning:* A document code printed on every
  page would otherwise fragment a logical section at each page break.
- *Fallback:* `.docx` → python-docx (heading styles mapped to markdown `#`);
  `.txt`/`.md`/`.csv` and PyMuPDF-less PDFs → line-based parser applying the same
  textual heading rules. If no headings are found, `_windowed_sections` packs
  paragraphs into ~`parent_max_tokens` windows so downstream agents always get
  coherent, offset-anchored input.

### Step 2 — Section embeddings

Each raw section is embedded (`text-embedding-3-large`, 3072-dim, L2-normalized).

- *Why here:* These vectors feed the merge similarity gate (step 3) — they
  decide *which* sections get the expensive LLM comparison, so they're computed
  once up front.

### Step 3 — Semantic section merge (`agents/section_merger.py`)

Adjacent sections describing one concept (e.g. "Bearing Failure Symptoms" +
"...Causes" + "...Corrective Actions") are fused into one `MergedSection`. A
**two-tier gate**:

1. **Structural rules resolve most merges for free** (`_structural_decision`):
   tables never merge with prose; a deeper heading level merges by containment;
   sub-`TINY_SECTION` (<40 token) fragments get absorbed.
2. Only genuine *siblings* fall through to a **cosine-similarity gate**
   (threshold 0.75), and only if that passes is **GPT-4o** asked "same concept?"
   — with the *next* section included as context.

- *Why the tiered gate:* The LLM call is the expensive step. Structural
  containment and the embedding threshold filter out the vast majority of pairs,
  so GPT is only paid for ambiguous siblings — an explicit cost optimization.
- *Why merge at all:* A "complete maintenance concept" (symptoms + causes + fixes
  together) is the right unit for a *parent* chunk — retrieval on a symptom
  should be able to surface the corresponding fix.
- *Why a running-mean embedding:* As sections merge, the concept's vector is
  updated incrementally (`_running_mean`) so the next similarity comparison
  reflects the whole accumulated concept, not just the first section.

### Steps 4–5 — Concept & relationship extraction (per merged section)

- **`ConceptExtractionAgent`** classifies each concept into a fixed taxonomy
  (`FAILURE_MODE`, `SOP`, `SPARE_PART`, `MAINTENANCE_TASK`, ...) and lists its
  semantic groups. Mutates the section in place.
- **`RelationshipExtractionAgent`** emits `(source, relation, target)` triples
  over a closed relation vocabulary (`HAS_SYMPTOM`, `HAS_CAUSE`, `CORRECTED_BY`,
  `REQUIRES_PART`, ...), building a **maintenance knowledge graph**.

- *Why a fixed taxonomy / closed relation set:* Both agents normalize LLM output
  against an allowlist (`_normalise_type`, `_normalise_relation`) and fall back
  to `OTHER`/`RELATED_TO`. This keeps the graph and index-routing logic
  deterministic despite free-form LLM output.
- *Why a knowledge graph alongside vectors:* Diagnosis is inherently relational
  ("this symptom → this cause → this fix"). Vectors find *similar* text; the
  graph supplies *causal* structure that's later injected into context and mined
  for root causes (search step 9).
- *Why JSON mode:* `response_format={"type": "json_object"}` at `temperature=0`
  (`rag/llm.py`) makes extraction parseable and reproducible.

### Step 6 — Chunk boundaries (`agents/chunk_boundary.py`)

Each concept becomes a **parent–child hierarchy**:

- **Parent** = whole concept (~1500–2500 tokens), split only if >1.4× max.
- **Children** = ~200–500 token semantic units, each tagged with a
  `semantic_type` by keyword scoring (`SYMPTOMS`, `ROOT_CAUSES`,
  `CORRECTIVE_ACTIONS`, ...).

Boundaries are packed along paragraph→sentence→char units so they **never cut
mid-word**; tables are emitted as a single child (never row-split). Returns
**offsets only**, text sliced from source.

- *Why parent/child (small-to-big retrieval):* You want to *embed and match* on
  small, focused units (a child about "symptoms" matches a symptom query
  precisely), but *feed the LLM* the full surrounding concept (the parent) so it
  has complete context. Children are the retrieval handle; parents are the
  context payload (search step 8).
- *Why tables stay whole:* A dimensional or spare-parts table loses all meaning
  if its rows are scattered across chunks.

### Steps 7–8 — Embedding & persistence with content-based routing

Only **child chunks** are embedded and added to a vector index; parents live
only in SQLite. Chunks/concepts/relationships are persisted via `RagRepository`
(SQLite). The index a child lands in is chosen by **content, not upload type**
(`_target_index`, `rag/ingestion.py`): an SOP section *inside* a document
uploaded as `MANUAL` is still routed to `sop_index`.

- *Why only embed children:* Parents are retrieved by ID via their children,
  never matched directly — embedding them would waste tokens and pollute the
  index with long, diffuse vectors.
- *Why content-based routing:* The retrieval strategies (below) weight indexes
  by intent. If routing followed upload type, a procedure buried in a manual
  would never get the SOP weighting it deserves. Routing by classified
  `section_type` keeps `sop_index`/`spare_part_index` correctly populated
  regardless of how the file was uploaded.

### Step 9 — Special structured extraction

For `FAILURE_REPORT` and `MAINTENANCE_LOG` uploads, dedicated extractors pull
structured records (failure_mode/root_cause/resolution/outcome, or
symptom/action/result) into their own SQLite tables **and** embed them into the
matching index.

- *Why:* Incident history is the highest-value signal for diagnosis. Storing it
  both as structured rows (for exact root-cause/resolution extraction) and as
  embeddings (for semantic recall) lets the search pipeline do both. A separate
  `ingest_records()` path handles bulk tabular dumps spanning many equipment —
  no LLM extraction, batched embedding at 256/call to respect OpenAI input
  limits.

---

## 2. Storage architecture

**Five separate per-doctype vector indexes** (`vectorstore.py`): `manual`,
`sop`, `failure_report`, `maintenance_log`, `spare_part` — not one combined
index.

- *Why split:* Intent-driven retrieval weights index *sources* differently (a
  `PROCEDURE` query trusts `sop_index` 0.50; a `DIAGNOSIS` trusts
  `failure_report_index` 0.40). Physically separate indexes make that weighting
  natural and let each index be searched or skipped independently.

Each index = an L2-normalized `.npy` matrix + a `.json` sidecar of payloads.

- **FAISS `IndexFlatIP`** when installed; **numpy brute-force dot product**
  otherwise. Both persist identically, so switching backends never invalidates
  data.
- *Why `IndexFlatIP` (exact, not approximate like IVF/HNSW):* At
  maintenance-corpus scale exact search is fast enough, and it avoids ANN recall
  loss and index-tuning overhead. Since vectors are L2-normalized, inner product
  = cosine.
- A dimension guard rejects mismatched vectors with a clear "delete
  data/vectorstore to rebuild" message — protecting against silent corruption
  when the embedding model changes.

---

## 3. Retrieval / search pipeline

`SearchPipeline.answer()` (`rag/search.py`), consumed by `AgentService`. Stages:

### Steps 1–2 — Equipment & intent detection

- **Equipment** (`EquipmentDetectionAgent`): deterministic, *not* an LLM — exact
  code match → loose code regex (`BF-101` ≈ `BF101`) → name match. If an
  `equipment_id` is passed explicitly, that wins.
- **Intent** (`IntentDetectionAgent`): GPT classifies into 6 intents
  (`DIAGNOSIS`, `ROOT_CAUSE`, `PROCEDURE`, `MAINTENANCE_PLAN`, `SPARE_PART`,
  `GENERAL_QA`).

- *Why deterministic equipment detection:* Equipment codes are exact strings; an
  LLM would add latency and a hallucination surface for something regex solves
  perfectly. Intent is fuzzy/linguistic, so it gets the LLM.

### Step 3 — Retrieval strategy

Intent maps to an `{index: weight}` table (`_STRATEGIES`). Incident indexes are
*always* added at low weight (`_INCIDENT_INDEXES`).

- *Why always consult incidents:* Past failures inform almost any maintenance
  question, so even a `PROCEDURE` query gets a small dose of historical-incident
  recall.

### Steps 4–5 — Multi-query expansion + hybrid retrieval

- **`QueryExpansionAgent`** generates up to 4 paraphrases (+ the original) using
  failure-mode terminology.
- For each query, **hybrid dense + BM25 lexical retrieval, RRF-fused per index**
  (`vectorstore.hybrid_search`).

- *Why query expansion:* One phrasing under-samples the concept space;
  paraphrases improve recall before ranking. Best evidence per item is kept
  across all expansions (max of semantic/lexical scores).
- *Why hybrid dense+sparse:* This is the crux. `text-embedding-3-large`
  systematically *under-weights exact alphanumeric tokens* — and those
  (`BF-101`, `E-401`, `6312-2RS`, `6.6kV`) are exactly what maintenance queries
  hinge on. A custom dependency-free BM25 (`lexical.py`) with a
  **code-preserving tokenizer** (`BF-101` stays one token) recovers exact
  matches dense retrieval misses.
- *Why RRF (Reciprocal Rank Fusion, k=60):* Dense cosine and BM25 produce
  incomparable score scales. RRF fuses by *rank*, not raw score, so neither
  ranker's magnitude dominates. The **union** of both top-k candidate sets is
  considered, so an exact-code hit the dense ranker missed still surfaces.
- **Equipment isolation:** when `equipment_id` is set, candidates are filtered to
  that equipment *before* ranking, so retrieval never crosses equipment
  boundaries.

### Steps 6–7 — Hybrid ranking + cross-encoder rerank

- **`_hybrid_rank`** computes a weighted `final_score`:
  `0.35·semantic + 0.15·lexical + 0.25·metadata(index weight) +
  0.15·equipment + 0.10·recency`.
- **`CrossEncoderReranker`** (`bge-reranker-large`) re-scores the top items
  against the query and keeps `rerank_top_k` (5).

- *Why this weighting:* Semantic stays dominant (0.35); lexical (0.15) breaks
  ties on exact codes; metadata folds in the intent→index strategy; equipment
  match and recency (newer incidents score higher via `1/(1+age/30d)`) act as
  priors. It's a genuine multi-signal hybrid, not just cosine.
- *Why a cross-encoder on top:* Bi-encoder retrieval scores query and doc
  *independently*; a cross-encoder reads them *jointly* and is far more accurate
  at fine-grained relevance — but too slow to run over the whole corpus. So it's
  applied only to the survivors. It's lazy-loaded once and silently falls back to
  hybrid-rank order if unavailable.

### Steps 8–9 — Parent expansion + graph expansion

- **Parent-chunk expansion** (`_expand_and_cite`): for each matched child, the
  full **parent** chunk is pulled from SQLite to form the context block (deduped
  per parent), plus citations.
- **Graph expansion** (`_graph_expansion`): relationships touching the retrieved
  concepts are pulled and rendered as `source --RELATION--> target` lines.

- *Why:* This is the payoff of the parent/child + graph design. You matched on a
  precise child but hand the LLM the *complete concept* and its *causal
  neighborhood* — small-to-big retrieval plus structured reasoning context.

### Steps 10–11 — Compression + generation

- **`_compress`** packs blocks into a `context_max_tokens` (3000) budget: the
  knowledge graph gets up to ⅓ of the budget first, then context blocks until the
  budget is hit (last block truncated).
- **`_generate_answer`** sends a maintenance-engineer system prompt + live
  equipment data (`extra_context`) + retrieved context to GPT-4o, with
  instructions to prefer live data and cite document names.

- *Why budget the graph separately:* The causal graph is high-density signal;
  guaranteeing it a slice prevents long prose blocks from crowding it out.
- *Why blend live data + documents:* The final prompt fuses *current* equipment
  state (health, sensors, alerts, spares) with *historical* knowledge — and is
  told to prefer live data for "current condition" questions.

In parallel, `_extract_diagnosis` mines structured root-causes/resolutions from
incident payloads and `HAS_CAUSE`/`CORRECTED_BY` graph edges, and `_confidence`
reports the top item's score — so the API returns structured diagnosis fields,
not just prose.

**Graceful retrieval edge case:** if nothing is indexed but live equipment data
exists, it still answers from `extra_context` (confidence 0.4); if truly nothing,
it returns an "upload documents" message rather than hallucinating.

---

## Summary of the "why" threads

| Decision | Rationale |
|---|---|
| No embedding fallback | Silent semantic→lexical degradation is worse than a 503 |
| Offset-only chunking | Verbatim source text; citation integrity; no chunk hallucination |
| Tiered merge (structural→embedding→LLM) | Pay for GPT only on genuinely ambiguous siblings |
| Parent/child chunks | Match small & precise, generate with full context (small-to-big) |
| Knowledge graph + vectors | Vectors find similar text; graph supplies causal structure for diagnosis |
| 5 per-doctype indexes | Intent-driven source weighting; independent search |
| Content-based index routing | An SOP in a manual still gets SOP treatment |
| Hybrid dense+BM25 / RRF | Embeddings miss exact codes/part-numbers; rank-fusion balances scales |
| Cross-encoder rerank on top-k only | Joint scoring accuracy where it's affordable |
| FAISS `IndexFlatIP` + numpy fallback | Exact search, no ANN tuning; runs anywhere |
