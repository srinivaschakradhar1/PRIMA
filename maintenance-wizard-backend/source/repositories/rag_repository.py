"""Repository for RAG persistence: chunks, concepts, relationships, and the
structured incident / maintenance-log knowledge bases."""

from __future__ import annotations

import json
import uuid

from database.connection import Database
from rag.models import (
    Chunk,
    Concept,
    IncidentRecord,
    MaintenanceLogRecord,
    Relationship,
)

_RAG_TABLES = (
    "knowledge_chunk",
    "knowledge_concept",
    "knowledge_relationship",
    "incident_record",
    "maintenance_log_record",
)


class RagRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    # -- inserts ---------------------------------------------------------
    async def insert_chunks(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        await self._db.executemany_and_commit(
            "INSERT OR REPLACE INTO knowledge_chunk "
            "(chunk_id, parent_chunk_id, document_id, equipment_id, equipment_type, "
            "document_type, concept, semantic_type, page, start_offset, end_offset, "
            "text, token_count, is_parent, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    c.chunk_id, c.parent_chunk_id, c.document_id, c.equipment_id,
                    c.equipment_type, c.document_type, c.concept, c.semantic_type,
                    c.page, c.start_offset, c.end_offset, c.text, c.token_count,
                    1 if c.is_parent else 0, c.created_at,
                )
                for c in chunks
            ],
        )

    async def insert_concepts(self, concepts: list[Concept]) -> None:
        if not concepts:
            return
        await self._db.executemany_and_commit(
            "INSERT INTO knowledge_concept "
            "(id, document_id, equipment_id, concept_name, concept_type, groups_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    str(uuid.uuid4()), c.document_id, c.equipment_id, c.concept_name,
                    c.concept_type, json.dumps(c.semantic_groups),
                )
                for c in concepts
            ],
        )

    async def insert_relationships(self, relationships: list[Relationship]) -> None:
        if not relationships:
            return
        await self._db.executemany_and_commit(
            "INSERT INTO knowledge_relationship "
            "(id, document_id, equipment_id, source, relation, target, concept) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    str(uuid.uuid4()), r.document_id, r.equipment_id, r.source,
                    r.relation, r.target, r.concept,
                )
                for r in relationships
            ],
        )

    async def insert_incidents(self, incidents: list[IncidentRecord]) -> None:
        if not incidents:
            return
        await self._db.executemany_and_commit(
            "INSERT INTO incident_record "
            "(id, document_id, equipment_id, failure_mode, symptoms_json, root_cause, "
            "resolution, outcome, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    rec.id, rec.document_id, rec.equipment_id, rec.failure_mode,
                    json.dumps(rec.symptoms), rec.root_cause, rec.resolution,
                    rec.outcome, rec.created_at,
                )
                for rec in incidents
            ],
        )

    async def insert_maintenance_logs(self, logs: list[MaintenanceLogRecord]) -> None:
        if not logs:
            return
        await self._db.executemany_and_commit(
            "INSERT INTO maintenance_log_record "
            "(id, document_id, equipment_id, symptom, action, result, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    rec.id, rec.document_id, rec.equipment_id, rec.symptom,
                    rec.action, rec.result, rec.created_at,
                )
                for rec in logs
            ],
        )

    # -- deletes ---------------------------------------------------------
    async def delete_by_document(self, document_id: str) -> None:
        for table in _RAG_TABLES:
            await self._db.execute_and_commit(
                f"DELETE FROM {table} WHERE document_id = ?", (document_id,)
            )

    # -- reads (search support) -----------------------------------------
    async def get_chunk(self, chunk_id: str) -> dict | None:
        row = await self._db.fetch_one(
            "SELECT * FROM knowledge_chunk WHERE chunk_id = ?", (chunk_id,)
        )
        return dict(row) if row else None

    async def get_chunks_for_document(self, document_id: str) -> list[dict]:
        """All chunks (parents first, then in reading order) for a document."""
        rows = await self._db.fetch_all(
            "SELECT * FROM knowledge_chunk WHERE document_id = ? "
            "ORDER BY is_parent DESC, start_offset ASC, chunk_id ASC",
            (document_id,),
        )
        return [dict(r) for r in rows]

    async def list_incident_symptom_groups(
        self, equipment_id: str | None
    ) -> list[list[str]]:
        """Symptoms from past failure reports, grouped by incident.

        Each row of the structured Incident Knowledge Base (``incident_record``)
        records the set of symptoms observed *together* in one incident
        (``symptoms_json``). Returning one inner list per incident preserves that
        co-occurrence — which symptoms accompanied which — so the conversation
        agent can ask about symptoms that historically appear alongside the ones
        the engineer reported. Malformed / empty JSON is skipped so a single bad
        row never breaks symptom enrichment.
        """
        if not equipment_id:
            return []
        rows = await self._db.fetch_all(
            "SELECT symptoms_json FROM incident_record WHERE equipment_id = ?",
            (equipment_id,),
        )
        groups: list[list[str]] = []
        for row in rows:
            raw = row["symptoms_json"]
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if isinstance(parsed, list):
                group = [str(s).strip() for s in parsed if str(s).strip()]
                if group:
                    groups.append(group)
        return groups

    async def get_relationships_for_concepts(
        self, equipment_id: str | None, concepts: list[str], limit: int = 40
    ) -> list[dict]:
        if not concepts:
            return []
        placeholders = ",".join("?" for _ in concepts)
        params: list[object] = list(concepts) + list(concepts)
        query = (
            "SELECT DISTINCT source, relation, target, concept FROM knowledge_relationship "
            f"WHERE (concept IN ({placeholders}) OR source IN ({placeholders}))"
        )
        if equipment_id:
            query += " AND (equipment_id = ? OR equipment_id IS NULL)"
            params.append(equipment_id)
        query += " LIMIT ?"
        params.append(limit)
        rows = await self._db.fetch_all(query, params)
        return [dict(r) for r in rows]

    async def stats_for_document(self, document_id: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for table in _RAG_TABLES:
            row = await self._db.fetch_one(
                f"SELECT COUNT(*) AS cnt FROM {table} WHERE document_id = ?", (document_id,)
            )
            out[table] = row["cnt"] if row else 0
        return out
