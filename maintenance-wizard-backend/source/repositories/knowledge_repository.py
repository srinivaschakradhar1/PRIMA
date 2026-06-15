"""Repository for the ``knowledge_document`` table."""

from __future__ import annotations

from database.connection import Database
from models.domain import KnowledgeDocument


class KnowledgeRepository:
    """Data access layer for knowledge document records."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def insert(self, document: KnowledgeDocument) -> None:
        await self._db.execute_and_commit(
            "INSERT INTO knowledge_document "
            "(id, equipment_id, document_name, document_type, file_path, file_hash, uploaded_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                document.id,
                document.equipment_id,
                document.document_name,
                document.document_type,
                document.file_path,
                document.file_hash,
                document.uploaded_at,
            ),
        )

    async def get_by_id(self, document_id: str) -> KnowledgeDocument | None:
        row = await self._db.fetch_one(
            "SELECT id, equipment_id, document_name, document_type, file_path, "
            "file_hash, uploaded_at FROM knowledge_document WHERE id = ?",
            (document_id,),
        )
        return KnowledgeDocument.from_row(row) if row else None

    async def update(self, document: KnowledgeDocument) -> None:
        await self._db.execute_and_commit(
            "UPDATE knowledge_document SET equipment_id = ?, document_name = ?, "
            "document_type = ?, file_path = ?, file_hash = ?, uploaded_at = ? "
            "WHERE id = ?",
            (
                document.equipment_id,
                document.document_name,
                document.document_type,
                document.file_path,
                document.file_hash,
                document.uploaded_at,
                document.id,
            ),
        )

    async def delete(self, document_id: str) -> None:
        await self._db.execute_and_commit(
            "DELETE FROM knowledge_document WHERE id = ?", (document_id,)
        )

    @staticmethod
    def _build_filters(
        equipment_type: str | None,
        equipment_id: str | None,
        document_type: str | None,
    ) -> tuple[str, list[object]]:
        """Build a shared WHERE clause (and params) for listing/counting."""
        clause = ""
        params: list[object] = []
        if equipment_type is not None:
            clause += " AND e.equipment_type = ?"
            params.append(equipment_type)
        if equipment_id is not None:
            clause += " AND kd.equipment_id = ?"
            params.append(equipment_id)
        if document_type is not None:
            clause += " AND kd.document_type = ?"
            params.append(document_type)
        return clause, params

    async def list_documents(
        self,
        equipment_type: str | None = None,
        equipment_id: str | None = None,
        document_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List ingested documents with their indexed chunk counts.

        ``chunk_count`` reflects only embedded chunks (``is_parent = 0``), which
        are the ones stored in the vector database. ``equipment_type`` is taken
        from the joined ``equipment`` record.
        """
        clause, params = self._build_filters(
            equipment_type, equipment_id, document_type
        )
        query = (
            "SELECT kd.id AS document_id, kd.equipment_id AS equipment_id, "
            "e.equipment_type AS equipment_type, kd.document_type AS document_type, "
            "kd.document_name AS document_name, kd.uploaded_at AS ingested_at, "
            "(SELECT COUNT(*) FROM knowledge_chunk kc "
            "WHERE kc.document_id = kd.id AND kc.is_parent = 0) AS chunk_count "
            "FROM knowledge_document kd "
            "LEFT JOIN equipment e ON e.id = kd.equipment_id "
            "WHERE 1=1" + clause + " "
            "ORDER BY kd.uploaded_at DESC, kd.id ASC "
            "LIMIT ? OFFSET ?"
        )
        rows = await self._db.fetch_all(query, params + [limit, offset])
        return [dict(row) for row in rows]

    async def count_documents(
        self,
        equipment_type: str | None = None,
        equipment_id: str | None = None,
        document_type: str | None = None,
    ) -> int:
        """Count ingested documents matching the given filters."""
        clause, params = self._build_filters(
            equipment_type, equipment_id, document_type
        )
        row = await self._db.fetch_one(
            "SELECT COUNT(*) AS cnt FROM knowledge_document kd "
            "LEFT JOIN equipment e ON e.id = kd.equipment_id "
            "WHERE 1=1" + clause,
            params,
        )
        return row["cnt"] if row else 0
