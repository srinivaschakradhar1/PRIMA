"""Ingestion pipeline orchestrator.

Implements the high-level ingestion pipeline from the technical design:

    parse -> section embeddings -> semantic merge -> concept extraction ->
    relationship extraction -> chunk boundaries -> embed child chunks ->
    per-type FAISS index + SQLite persistence (+ special extraction for
    FAILURE_REPORT / MAINTENANCE_LOG).

Invoked by :class:`services.knowledge_service.KnowledgeService` on document
upload / replace.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag.agents.chunk_boundary import ChunkBoundaryAgent
from rag.agents.concept_extraction import ConceptExtractionAgent
from rag.agents.relationship_extraction import RelationshipExtractionAgent
from rag.agents.section_merger import SemanticSectionMergerAgent
from rag.agents.special_extraction import FailureReportExtractor, MaintenanceLogExtractor
from rag.embeddings import embedding_client
from rag.models import Chunk, Concept
from rag.parsing import parse_document
from rag.record_loader import build_failure_chunks, build_maintenance_chunks
from rag.vectorstore import index_name_for_doctype, vector_store

logger = logging.getLogger(__name__)

# Upload types whose chunks are pinned to their own index regardless of content.
_PINNED_DOCTYPES = {"FAILURE_REPORT", "MAINTENANCE_LOG"}

# Embed structured records in batches so a single large file does not exceed the
# OpenAI embeddings input-array / token limits.
_RECORD_EMBED_BATCH = 256


def _target_index(document_type: str, ms) -> str:
    """Choose the vector index for a concept by its classified content type.

    This is what keeps the ``sop_index`` / ``spare_part_index`` (referenced by the
    search retrieval strategies) populated: an SOP or spare-parts section is routed
    there even when the document was uploaded as a generic MANUAL.
    """
    dt = (document_type or "MANUAL").upper()
    if dt in _PINNED_DOCTYPES:
        return index_name_for_doctype(dt)
    section_type = (getattr(ms, "section_type", "") or "").upper()
    if dt == "SOP" or section_type == "SOP":
        return index_name_for_doctype("SOP")
    if dt == "SPARE_PART" or section_type == "SPARE_PART":
        return index_name_for_doctype("SPARE_PART")
    return index_name_for_doctype(dt)


class IngestionPipeline:
    def __init__(self, rag_repository, equipment_repository) -> None:
        self._repo = rag_repository
        self._equipment_repo = equipment_repository
        self._merger = SemanticSectionMergerAgent()
        self._concept_agent = ConceptExtractionAgent()
        self._relationship_agent = RelationshipExtractionAgent()
        self._chunker = ChunkBoundaryAgent()
        self._failure_extractor = FailureReportExtractor()
        self._log_extractor = MaintenanceLogExtractor()
        self._vs = vector_store

    async def ingest(
        self,
        file_path: Path,
        document_id: str,
        equipment_id: str | None,
        document_type: str | None,
    ) -> dict[str, Any]:
        document_type = (document_type or "MANUAL").upper()
        logger.info("RAG ingest start: doc=%s type=%s file=%s", document_id, document_type, file_path.name)

        # 1. Parse into offset-anchored sections.
        full_text, sections = parse_document(file_path)
        if not sections:
            logger.warning("No extractable content in %s; nothing indexed.", file_path.name)
            return {"sections": 0, "chunks": 0, "indexed": 0}

        # 2. Equipment metadata for chunk tagging / filtering.
        equipment_type = await self._equipment_type(equipment_id)

        # 3. Section embeddings (drive the merge similarity gate).
        section_embeddings = await embedding_client.embed([s.text for s in sections])

        # 4. Semantic section merge.
        merged_sections = await self._merger.run(full_text, sections, section_embeddings)

        # 5. Per concept: classify, extract relationships, compute chunk boundaries.
        all_chunks: list[Chunk] = []
        all_concepts: list[Concept] = []
        all_relationships = []
        children_by_index: dict[str, list[Chunk]] = {}
        for ms in merged_sections:
            await self._concept_agent.run(ms)
            all_relationships.extend(
                await self._relationship_agent.run(ms, document_id, equipment_id)
            )
            section_chunks = self._chunker.run(
                ms,
                document_id=document_id,
                equipment_id=equipment_id,
                equipment_type=equipment_type,
                document_type=document_type,
            )
            all_chunks.extend(section_chunks)

            # Route this concept's children to the index that matches its *content*
            # (an SOP section inside a MANUAL still belongs in the SOP index), not
            # just the upload document_type.
            target_index = _target_index(document_type, ms)
            for chunk in section_chunks:
                if not chunk.is_parent and chunk.text.strip():
                    children_by_index.setdefault(target_index, []).append(chunk)

            all_concepts.append(
                Concept(
                    document_id=document_id,
                    equipment_id=equipment_id,
                    concept_name=ms.concept_name,
                    concept_type=ms.concept_type,
                    semantic_groups=ms.semantic_groups,
                )
            )

        # 6. Persist chunks + knowledge graph.
        await self._repo.insert_chunks(all_chunks)
        await self._repo.insert_concepts(all_concepts)
        await self._repo.insert_relationships(all_relationships)

        # 7. Embed child chunks and add to their content-routed indexes.
        indexed = await self._index_children(children_by_index)

        # 8. Special structured extraction for incidents / logs.
        special = await self._special_extraction(
            full_text, document_id, equipment_id, equipment_type, document_type
        )

        summary = {
            "sections": len(sections),
            "merged_concepts": len(merged_sections),
            "chunks": len(all_chunks),
            "parents": sum(1 for c in all_chunks if c.is_parent),
            "relationships": len(all_relationships),
            "indexed": indexed,
            **special,
        }
        logger.info("RAG ingest complete: doc=%s %s", document_id, summary)
        return summary

    async def remove_document(self, document_id: str) -> None:
        await self._repo.delete_by_document(document_id)
        await asyncio.to_thread(self._vs.remove_document, document_id)
        logger.info("RAG removal complete for document %s.", document_id)

    async def get_document_chunks(self, document_id: str) -> list[dict[str, Any]]:
        """Return every chunk of a document annotated with its vector index.

        Parent chunks live only in the relational store (used for context
        expansion) and are not embedded, so their ``index_name`` is ``None``;
        child chunks carry the name of the index they were routed into.
        """
        chunks = await self._repo.get_chunks_for_document(document_id)
        index_map = await asyncio.to_thread(self._vs.index_map_for_document, document_id)
        return [
            {
                "chunk_id": c.get("chunk_id"),
                "parent_chunk_id": c.get("parent_chunk_id"),
                "is_parent": bool(c.get("is_parent")),
                "index_name": index_map.get(c.get("chunk_id")),
                "document_type": c.get("document_type"),
                "concept": c.get("concept"),
                "semantic_type": c.get("semantic_type"),
                "page": c.get("page"),
                "start_offset": c.get("start_offset"),
                "end_offset": c.get("end_offset"),
                "token_count": c.get("token_count"),
                "text": c.get("text") or "",
            }
            for c in chunks
        ]

    # -- helpers ---------------------------------------------------------
    async def _equipment_type(self, equipment_id: str | None) -> str | None:
        if not equipment_id:
            return None
        equipment = await self._equipment_repo.get_by_id(equipment_id)
        return equipment.equipment_type if equipment else None

    async def _index_children(self, children_by_index: dict[str, list[Chunk]]) -> int:
        total = 0
        for index_name, children in children_by_index.items():
            if not children:
                continue
            vectors = await embedding_client.embed([c.text for c in children])
            entries = [
                {
                    "kind": "chunk",
                    "ref_id": c.chunk_id,
                    "parent_chunk_id": c.parent_chunk_id,
                    "document_id": c.document_id,
                    "equipment_id": c.equipment_id,
                    "equipment_type": c.equipment_type,
                    "document_type": c.document_type,
                    "concept": c.concept,
                    "semantic_type": c.semantic_type,
                    "is_table": c.is_table,
                    "page": c.page,
                    "text": c.text,
                    "created_at": (c.created_at or datetime.now(timezone.utc)).isoformat(),
                }
                for c in children
            ]
            await asyncio.to_thread(self._vs.add, index_name, vectors, entries)
            total += len(children)
        return total

    async def _special_extraction(
        self,
        full_text: str,
        document_id: str,
        equipment_id: str | None,
        equipment_type: str | None,
        document_type: str,
    ) -> dict[str, int]:
        now_iso = datetime.now(timezone.utc).isoformat()
        if document_type == "FAILURE_REPORT":
            incidents = await self._failure_extractor.run(full_text, document_id, equipment_id)
            await self._repo.insert_incidents(incidents)
            if incidents:
                vectors = await embedding_client.embed([rec.as_text() for rec in incidents])
                entries = [
                    {
                        "kind": "incident", "ref_id": rec.id, "document_id": document_id,
                        "equipment_id": equipment_id, "equipment_type": equipment_type,
                        "document_type": "FAILURE_REPORT",
                        "concept": rec.failure_mode, "semantic_type": "FAILURE_MODE",
                        "failure_mode": rec.failure_mode, "root_cause": rec.root_cause,
                        "resolution": rec.resolution, "outcome": rec.outcome,
                        "page": 1, "text": rec.as_text(), "created_at": now_iso,
                    }
                    for rec in incidents
                ]
                await asyncio.to_thread(
                    self._vs.add, index_name_for_doctype("FAILURE_REPORT"), vectors, entries
                )
            return {"incidents": len(incidents)}

        if document_type == "MAINTENANCE_LOG":
            logs = await self._log_extractor.run(full_text, document_id, equipment_id)
            await self._repo.insert_maintenance_logs(logs)
            if logs:
                vectors = await embedding_client.embed([rec.as_text() for rec in logs])
                entries = [
                    {
                        "kind": "maintenance_log", "ref_id": rec.id, "document_id": document_id,
                        "equipment_id": equipment_id, "equipment_type": equipment_type,
                        "document_type": "MAINTENANCE_LOG",
                        "concept": rec.symptom, "semantic_type": "MAINTENANCE_TASK",
                        "symptom": rec.symptom, "action": rec.action, "result": rec.result,
                        "page": 1, "text": rec.as_text(), "created_at": now_iso,
                    }
                    for rec in logs
                ]
                await asyncio.to_thread(
                    self._vs.add, index_name_for_doctype("MAINTENANCE_LOG"), vectors, entries
                )
            return {"maintenance_logs": len(logs)}

        return {}

    # -- structured-record ingestion -------------------------------------
    async def ingest_records(
        self,
        records: list[dict[str, Any]],
        document_type: str,
        document_id: str,
    ) -> dict[str, int]:
        """Ingest a list of already-structured records (no LLM extraction).

        Used by the bulk multi-equipment ingestion path for tabular dumps where
        one file holds many records spanning many equipment. Each record's
        equipment is validated, high-signal text is embedded, the full record is
        stored as the vector payload (stamped with the real event date), and a
        structured incident / maintenance-log row is persisted.
        """
        dt = (document_type or "").upper()

        if dt == "FAILURE_REPORT":
            result = build_failure_chunks(records, document_id, self._equipment_repo)
            await self._repo.insert_incidents(result.incidents)
        elif dt == "MAINTENANCE_LOG":
            result = build_maintenance_chunks(records, document_id, self._equipment_repo)
            await self._repo.insert_maintenance_logs(result.logs)
        else:
            raise ValueError(
                f"ingest_records only supports FAILURE_REPORT / MAINTENANCE_LOG, got {document_type!r}"
            )

        indexed = await self._index_entries(index_name_for_doctype(dt), result.entries)
        summary = dict(result.stats)
        summary["embeddings"] = indexed
        logger.info("Record ingest complete: doc=%s type=%s %s", document_id, dt, summary)
        return summary

    async def _index_entries(
        self, index_name: str, entries: list[tuple[str, dict[str, Any]]]
    ) -> int:
        """Embed (text, payload) pairs in batches and add them to one index."""
        total = 0
        for start in range(0, len(entries), _RECORD_EMBED_BATCH):
            batch = entries[start : start + _RECORD_EMBED_BATCH]
            if not batch:
                continue
            vectors = await embedding_client.embed([text for text, _ in batch])
            payloads = [payload for _, payload in batch]
            await asyncio.to_thread(self._vs.add, index_name, vectors, payloads)
            total += len(payloads)
        return total

    async def _valid_equipment_ids(self, records: list[dict[str, Any]]) -> set[str]:
        """Return the subset of referenced equipment ids that actually exist."""
        ids = {
            str(r.get("equipment_id") or "").strip()
            for r in records
            if str(r.get("equipment_id") or "").strip()
        }
        valid: set[str] = set()
        for eid in ids:
            if await self._equipment_repo.exists(eid):
                valid.add(eid)
        return valid
