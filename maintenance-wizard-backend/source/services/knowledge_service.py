"""Service layer for knowledge document management."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

from models.domain import KnowledgeDocument, Equipment
from rag.errors import OpenAIUnavailableError
from rag.ingestion import IngestionPipeline
from rag.record_loader import RecordParseError, load_records
from repositories.equipment_repository import EquipmentRepository
from repositories.knowledge_repository import KnowledgeRepository
from services.ingestion_jobs import BulkIngestJob, FileResult, job_store

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge_documents"


class KnowledgeDocumentNotFoundError(Exception):
    """Raised when a knowledge document cannot be found."""


class EquipmentNotFoundError(Exception):
    """Raised when the referenced equipment does not exist."""


class FolderNotFoundError(Exception):
    """Raised when a bulk-ingest folder path is missing or not a directory."""


class InvalidRecordFileError(Exception):
    """Raised when an uploaded record file is malformed or unsupported."""


# Document types the structured-record ingestion path supports.
_RECORD_DOCUMENT_TYPES = {"FAILURE_REPORT", "MAINTENANCE_LOG"}


class KnowledgeService:
    """Business logic for uploading, replacing, and deleting knowledge documents."""

    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        equipment_repository: EquipmentRepository,
        ingestion_pipeline: IngestionPipeline,
    ) -> None:
        self._knowledge_repository = knowledge_repository
        self._equipment_repository = equipment_repository
        self._ingestion = ingestion_pipeline

    async def upload_document(
        self, contents: bytes, filename: str, equipment_id: str, document_type: str
    ) -> str:
        """Store and ingest already-read file bytes for a single equipment.

        Accepts the raw ``contents`` (and original ``filename``) rather than the
        ``UploadFile`` itself: the SSE upload endpoint runs this in a background
        task that executes only while the streaming response is iterated, by which
        point Starlette has already closed the request's ``UploadFile``. Reading
        the bytes in the request handler and passing them here avoids an
        "I/O operation on closed file" error.
        """
        if not await self._equipment_repository.exists(equipment_id):
            raise EquipmentNotFoundError(equipment_id)

        return await self._store_and_ingest(
            contents, filename, equipment_id, document_type
        )

    async def _store_and_ingest(
        self,
        contents: bytes,
        original_filename: str,
        equipment_id: str,
        document_type: str,
    ) -> str:
        """Persist file bytes to disk, run the RAG pipeline, and record metadata.

        Shared by the single-file upload and the bulk folder ingestion paths. The
        ``KnowledgeDocument`` row is inserted only after ``_extract_chunk_embed_index``
        returns, so an OpenAI failure (which it re-raises) leaves no orphan record.
        """
        document_id = str(uuid.uuid4())
        file_hash = hashlib.sha256(contents).hexdigest()

        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        file_path = STORAGE_DIR / f"{document_id}_{original_filename}"
        file_path.write_bytes(contents)

        await self._extract_chunk_embed_index(
            file_path, document_id, equipment_id, document_type
        )

        document = KnowledgeDocument(
            id=document_id,
            equipment_id=equipment_id,
            document_name=original_filename,
            document_type=document_type,
            file_path=str(file_path),
            file_hash=file_hash,
            uploaded_at=datetime.now(timezone.utc),
        )
        await self._knowledge_repository.insert(document)

        return document_id

    async def start_bulk_ingest(
        self, folder_path: str, document_type: str
    ) -> BulkIngestJob:
        """Acknowledge a bulk folder ingestion and run it in the background.

        Lists the files in ``folder_path`` (each named ``equipmentId_filename``),
        registers a job, and schedules ``_run_bulk_ingest`` as a background
        ``asyncio`` task. Returns immediately without awaiting ingestion so the
        request thread is never blocked.
        """
        folder = Path(folder_path)
        if not folder.is_dir():
            raise FolderNotFoundError(folder_path)

        files = sorted(p for p in folder.iterdir() if p.is_file())
        job = job_store.create(
            folder_path=str(folder), document_type=document_type, total=len(files)
        )

        task = asyncio.create_task(self._run_bulk_ingest(job, files, document_type))
        job_store.attach_task(job.job_id, task)

        return job

    async def _run_bulk_ingest(
        self, job: BulkIngestJob, files: list[Path], document_type: str
    ) -> None:
        """Ingest each file sequentially, recording per-file outcomes on the job.

        Files are processed one at a time to avoid overwhelming the OpenAI API and
        to limit SQLite-lock contention. Any per-file failure is logged and recorded
        but never aborts the batch.
        """
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)

        for path in files:
            name = path.name
            equipment_code: str | None = None
            try:
                if "_" not in name:
                    self._record_failure(
                        job, name, None,
                        "File name does not contain an equipment id prefix "
                        "(expected 'equipmentId_filename').",
                    )
                    continue

                equipment_code, original_filename = name.split("_", 1)
                equipment: Equipment | None = await self._equipment_repository.get_by_code(equipment_code)

                if not equipment:
                    self._record_failure(
                        job, name, equipment_code,
                        f"Equipment '{equipment_code}' not found.",
                    )
                    continue

                contents = path.read_bytes()
                document_id = await self._store_and_ingest(
                    contents, name, equipment.id, document_type
                )
                job.results.append(
                    FileResult(
                        file_name=name,
                        equipment_id=equipment_code,
                        document_id=document_id,
                        status="succeeded",
                    )
                )
                job.succeeded += 1
            except Exception as exc:  # noqa: BLE001 - one bad file must not abort the batch
                logger.exception("Bulk ingestion failed for file %s", path)
                self._record_failure(job, name, equipment_code, str(exc))
            finally:
                job.processed += 1

        job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)

    @staticmethod
    def _record_failure(
        job: BulkIngestJob, file_name: str, equipment_id: str | None, error: str
    ) -> None:
        job.results.append(
            FileResult(
                file_name=file_name,
                equipment_id=equipment_id,
                document_id=None,
                status="failed",
                error=error,
            )
        )
        job.failed += 1

    def get_bulk_job(self, job_id: str) -> BulkIngestJob | None:
        """Return the tracked bulk ingestion job, or ``None`` if unknown."""
        return job_store.get(job_id)

    async def start_bulk_record_ingest(
        self, file: UploadFile, document_type: str
    ) -> BulkIngestJob:
        """Acknowledge ingestion of a multi-equipment record file and run it async.

        Unlike the single-document upload, the file (JSON or CSV) holds many
        records that each belong to a different equipment; the equipment id is
        read from each record's mandatory ``equipment_id`` field. The file is
        parsed and validated synchronously (so malformed input fails fast with a
        4xx), then embedding/indexing runs in a background task tracked by a job.
        """
        doc_type = (document_type or "").upper()
        if doc_type not in _RECORD_DOCUMENT_TYPES:
            raise InvalidRecordFileError(
                "documentType must be FAILURE_REPORT or MAINTENANCE_LOG for record ingestion."
            )

        contents = await file.read()
        try:
            records = load_records(contents, file.filename, doc_type)
        except RecordParseError as exc:
            raise InvalidRecordFileError(str(exc)) from exc

        # One dataset document represents the whole file; per-record equipment ids
        # live on the chunks / structured rows, so the document is equipment-agnostic.
        document_id = str(uuid.uuid4())
        file_hash = hashlib.sha256(contents).hexdigest()
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        file_path = STORAGE_DIR / f"{document_id}_{file.filename}"
        file_path.write_bytes(contents)

        document = KnowledgeDocument(
            id=document_id,
            equipment_id=None,
            document_name=file.filename,
            document_type=doc_type,
            file_path=str(file_path),
            file_hash=file_hash,
            uploaded_at=datetime.now(timezone.utc),
        )
        await self._knowledge_repository.insert(document)

        job = job_store.create(
            folder_path=file.filename or "", document_type=doc_type, total=len(records)
        )
        task = asyncio.create_task(
            self._run_record_ingest(job, records, doc_type, document_id, file.filename)
        )
        job_store.attach_task(job.job_id, task)
        return job

    async def _run_record_ingest(
        self,
        job: BulkIngestJob,
        records: list[dict],
        document_type: str,
        document_id: str,
        file_name: str | None,
    ) -> None:
        """Embed + index the parsed records in the background, updating the job."""
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        try:
            summary = await self._ingestion.ingest_records(
                records=records, document_type=document_type, document_id=document_id
            )
            job.embeddings = summary.get("embeddings", 0)
            job.indexed_records = summary.get("incidents", 0) or summary.get(
                "maintenance_logs", 0
            )
            job.skipped_na = summary.get("skipped_na", 0)
            job.skipped_unknown_equipment = summary.get("skipped_unknown", 0)
            job.succeeded = job.indexed_records
            job.failed = job.skipped_na + job.skipped_unknown_equipment
            job.processed = job.total
            job.results.append(
                FileResult(
                    file_name=file_name or "",
                    equipment_id=None,
                    document_id=document_id,
                    status="succeeded",
                )
            )
        except Exception as exc:  # noqa: BLE001 - record outcome, never crash the task
            logger.exception("Record ingestion failed for document %s", document_id)
            job.processed = job.total
            job.failed = job.total
            job.results.append(
                FileResult(
                    file_name=file_name or "",
                    equipment_id=None,
                    document_id=document_id,
                    status="failed",
                    error=str(exc),
                )
            )
        finally:
            job.status = "completed"
            job.finished_at = datetime.now(timezone.utc)

    async def replace_document(
        self,
        document_id: str,
        file: UploadFile,
        equipment_id: str | None,
        document_type: str | None,
    ) -> str:
        existing = await self._knowledge_repository.get_by_id(document_id)
        if existing is None:
            raise KnowledgeDocumentNotFoundError(document_id)

        if equipment_id is not None and not await self._equipment_repository.exists(
            equipment_id
        ):
            raise EquipmentNotFoundError(equipment_id)

        await self._remove_vectors_and_chunks(document_id)

        if existing.file_path:
            old_path = Path(existing.file_path)
            if old_path.exists():
                old_path.unlink()

        contents = await file.read()
        file_hash = hashlib.sha256(contents).hexdigest()

        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        new_file_path = STORAGE_DIR / f"{document_id}_{file.filename}"
        new_file_path.write_bytes(contents)

        effective_equipment_id = equipment_id if equipment_id is not None else existing.equipment_id
        effective_document_type = (
            document_type if document_type is not None else existing.document_type
        )
        await self._extract_chunk_embed_index(
            new_file_path, document_id, effective_equipment_id, effective_document_type
        )

        existing.document_name = file.filename
        existing.file_path = str(new_file_path)
        existing.file_hash = file_hash
        existing.uploaded_at = datetime.now(timezone.utc)
        if equipment_id is not None:
            existing.equipment_id = equipment_id
        if document_type is not None:
            existing.document_type = document_type

        await self._knowledge_repository.update(existing)

        return document_id

    async def list_documents(
        self,
        equipment_type: str | None = None,
        equipment_id: str | None = None,
        document_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Return a paginated list of ingested documents and the total count.

        Each item carries the document/equipment tagging, the number of chunks
        the document has in the vector database, and its ingestion timestamp.
        The ``total`` reflects all documents matching the filters, ignoring
        pagination.
        """
        documents = await self._knowledge_repository.list_documents(
            equipment_type=equipment_type,
            equipment_id=equipment_id,
            document_type=document_type,
            limit=limit,
            offset=offset,
        )
        total = await self._knowledge_repository.count_documents(
            equipment_type=equipment_type,
            equipment_id=equipment_id,
            document_type=document_type,
        )
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "documents": documents,
        }

    async def get_document_chunks(self, document_id: str) -> dict:
        """Return all chunks for a document plus the index each is stored in."""
        document = await self._knowledge_repository.get_by_id(document_id)
        if document is None:
            raise KnowledgeDocumentNotFoundError(document_id)

        chunks = await self._ingestion.get_document_chunks(document_id)
        counts_by_index: dict[str, int] = {}
        for chunk in chunks:
            index_name = chunk.get("index_name")
            if index_name:
                counts_by_index[index_name] = counts_by_index.get(index_name, 0) + 1

        return {
            "document_id": document_id,
            "document_name": document.document_name,
            "total_chunks": len(chunks),
            "indexed_chunks": sum(counts_by_index.values()),
            "counts_by_index": counts_by_index,
            "chunks": chunks,
        }

    async def get_document_file(self, document_id: str) -> tuple[Path, str]:
        """Return the stored file path and original name for a document.

        Raises ``KnowledgeDocumentNotFoundError`` if the document record is
        missing or its file is no longer present on disk.
        """
        document = await self._knowledge_repository.get_by_id(document_id)
        if document is None or not document.file_path:
            raise KnowledgeDocumentNotFoundError(document_id)

        file_path = Path(document.file_path)
        if not file_path.exists():
            raise KnowledgeDocumentNotFoundError(document_id)

        return file_path, document.document_name or file_path.name

    async def delete_document(self, document_id: str) -> bool:
        existing = await self._knowledge_repository.get_by_id(document_id)
        if existing is None:
            return False

        if existing.file_path:
            file_path = Path(existing.file_path)
            if file_path.exists():
                file_path.unlink()

        await self._remove_vectors_and_chunks(document_id)
        await self._knowledge_repository.delete(document_id)

        return True

    async def _extract_chunk_embed_index(
        self,
        file_path: Path,
        document_id: str,
        equipment_id: str | None,
        document_type: str | None,
    ) -> None:
        """Run the RAG ingestion pipeline: parse, merge, chunk, embed, index.

        An OpenAI connectivity failure is re-raised so the upload fails loudly
        (a 503 to the client) rather than silently persisting a document with no
        usable index. Other unexpected errors are logged but do not abort the
        upload, so the document and its metadata are still persisted and the index
        can be rebuilt by re-uploading.
        """
        try:
            summary = await self._ingestion.ingest(
                file_path=file_path,
                document_id=document_id,
                equipment_id=equipment_id,
                document_type=document_type,
            )
            logger.info("RAG ingestion for document %s: %s", document_id, summary)
        except OpenAIUnavailableError:
            logger.error("RAG ingestion aborted for document %s: OpenAI unavailable", document_id)
            raise
        except Exception:  # noqa: BLE001 - keep upload resilient to non-LLM RAG errors
            logger.exception("RAG ingestion failed for document %s", document_id)

    async def _remove_vectors_and_chunks(self, document_id: str) -> None:
        """Remove vectors, chunk metadata, graph and extractions for a document."""
        try:
            await self._ingestion.remove_document(document_id)
        except Exception:  # noqa: BLE001
            logger.exception("RAG removal failed for document %s", document_id)
