"""Pydantic schemas for the Knowledge Document resource."""

from __future__ import annotations

from datetime import datetime

from models.enums import DocumentType
from schemas.common import CamelModel


class KnowledgeUploadResponse(CamelModel):
    """Response schema for knowledge document upload/replace endpoints."""

    document_id: str


class KnowledgeDeleteResponse(CamelModel):
    """Response schema for knowledge document deletion."""

    status: str


class BulkIngestRequest(CamelModel):
    """Request to ingest every file in a server-accessible folder.

    Each file is expected to be named ``equipmentId_filename`` so the equipment id
    can be parsed from the file name; ``document_type`` applies to all files.
    """

    folder_path: str
    document_type: DocumentType


class BulkIngestAcceptedResponse(CamelModel):
    """Acknowledgement returned immediately when a bulk job is scheduled.

    ``accepted_files`` counts files for folder ingestion and records for the
    multi-equipment record-ingestion endpoint.
    """

    job_id: str
    status: str
    accepted_files: int


class BulkIngestFileResult(CamelModel):
    """Outcome of ingesting one file within a bulk job."""

    file_name: str
    equipment_id: str | None = None
    document_id: str | None = None
    status: str
    error: str | None = None


class BulkIngestJobStatusResponse(CamelModel):
    """Progress and per-file results for a bulk ingestion job."""

    job_id: str
    status: str
    folder_path: str
    document_type: str
    total: int
    processed: int
    succeeded: int
    failed: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    results: list[BulkIngestFileResult]
    # Record-ingestion counters (0 for file/folder jobs).
    embeddings: int = 0
    indexed_records: int = 0
    skipped_na: int = 0
    skipped_unknown_equipment: int = 0


class KnowledgeChunk(CamelModel):
    """A single stored chunk and the vector index it was routed into."""

    chunk_id: str
    parent_chunk_id: str | None = None
    is_parent: bool
    # Vector index the chunk is stored in; null for parent chunks, which are
    # persisted only in the relational store and are not embedded/indexed.
    index_name: str | None = None
    document_type: str | None = None
    concept: str | None = None
    semantic_type: str | None = None
    page: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    token_count: int | None = None
    text: str


class KnowledgeChunksResponse(CamelModel):
    """All chunks stored for a document, grouped by where they are indexed."""

    document_id: str
    document_name: str | None = None
    total_chunks: int
    indexed_chunks: int
    counts_by_index: dict[str, int]
    chunks: list[KnowledgeChunk]


class KnowledgeDocumentSummary(CamelModel):
    """Summary of a single ingested document for the listing endpoint."""

    document_id: str
    equipment_id: str | None = None
    # Type of the equipment the document is tagged against (from the equipment
    # record), distinct from ``document_type`` below.
    equipment_type: str | None = None
    document_type: str | None = None
    document_name: str | None = None
    # Number of embedded/indexed chunks the document has in the vector database.
    # Parent chunks are persisted only relationally and are not counted.
    chunk_count: int
    ingested_at: datetime | None = None


class KnowledgeDocumentListResponse(CamelModel):
    """Paginated list of ingested documents with a total count."""

    total: int
    limit: int
    offset: int
    documents: list[KnowledgeDocumentSummary]
