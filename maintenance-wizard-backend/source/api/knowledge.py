"""API routes for knowledge document management."""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from api.deps import get_knowledge_service
from api.exceptions import NotFoundError
from models.enums import DocumentType
from schemas.knowledge import (
    BulkIngestAcceptedResponse,
    BulkIngestJobStatusResponse,
    BulkIngestRequest,
    KnowledgeChunksResponse,
    KnowledgeDeleteResponse,
    KnowledgeDocumentListResponse,
    KnowledgeUploadResponse,
)
from services.knowledge_service import (
    EquipmentNotFoundError,
    FolderNotFoundError,
    InvalidRecordFileError,
    KnowledgeDocumentNotFoundError,
    KnowledgeService,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Knowledge"])

# How often to emit a keep-alive while the (potentially long) ingestion runs, so
# the UI's connection does not time out waiting for the final response.
_HEARTBEAT_SECONDS = 5.0


def _sse(event: str, data: dict) -> str:
    """Format a single Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/knowledge", response_model=KnowledgeDocumentListResponse)
async def list_knowledge_documents(
    equipmentType: str | None = Query(default=None),
    equipmentId: str | None = Query(default=None),
    documentType: DocumentType | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeDocumentListResponse:
    """List ingested documents with optional equipment/document-type filters.

    Each item reports how many chunks the document has in the vector database
    and when it was ingested. ``total`` is the count across all matches,
    independent of pagination.
    """
    data = await service.list_documents(
        equipment_type=equipmentType,
        equipment_id=equipmentId,
        document_type=documentType.value if documentType else None,
        limit=limit,
        offset=offset,
    )
    return KnowledgeDocumentListResponse(**data)


@router.post("/knowledge/upload")
async def upload_knowledge_document(
    file: UploadFile = File(...),
    equipmentId: str = Form(...),
    documentType: DocumentType = Form(...),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> StreamingResponse:
    """Upload and ingest a single knowledge document, streamed over SSE.

    Because storing the file and running the RAG pipeline (chunking, embedding,
    indexing) can take a while, the endpoint streams ``heartbeat`` events every 5
    seconds until ingestion finishes, then a final ``message`` event carrying the
    :class:`KnowledgeUploadResponse` payload (camelCase). A missing equipment or
    any failure arrives as an ``error`` event.
    """

    # Read the upload here, while the request (and its UploadFile) is still open.
    # event_stream() runs as the response is streamed, *after* this handler returns
    # and Starlette has closed the UploadFile, so a deferred file.read() would fail.
    contents = await file.read()
    filename = file.filename

    async def event_stream():
        task = asyncio.create_task(
            service.upload_document(
                contents=contents,
                filename=filename,
                equipment_id=equipmentId,
                document_type=documentType.value,
            )
        )
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=_HEARTBEAT_SECONDS)
                if task in done:
                    break
                yield _sse("heartbeat", {"ts": datetime.now(timezone.utc).isoformat()})
            document_id = task.result()  # re-raises any error from upload_document
            yield _sse(
                "message",
                KnowledgeUploadResponse(document_id=document_id).model_dump(),
            )
        except EquipmentNotFoundError:
            yield _sse("error", {"detail": "Equipment not found"})
        except Exception:  # pragma: no cover - defensive
            logger.exception("Knowledge document upload failed")
            if not task.done():
                task.cancel()
            yield _sse("error", {"detail": "Internal error while ingesting the document."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering so events flush live
        },
    )


@router.post(
    "/knowledge/bulk-upload",
    response_model=BulkIngestAcceptedResponse,
    status_code=202,
)
async def bulk_ingest_knowledge_documents(
    request: BulkIngestRequest,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> BulkIngestAcceptedResponse:
    """Ingest every file in a server-accessible folder asynchronously.

    Each file must be named ``equipmentId_filename`` so the equipment id can be
    parsed from the file name; ``documentType`` is applied to all files. The
    request is acknowledged immediately with a ``jobId`` while ingestion runs in a
    background task. Poll ``GET /knowledge/bulk-upload/{jobId}`` for progress.
    """
    try:
        job = await service.start_bulk_ingest(
            folder_path=request.folder_path,
            document_type=request.document_type.value,
        )
    except FolderNotFoundError as exc:
        raise NotFoundError("Folder not found") from exc

    return BulkIngestAcceptedResponse(
        job_id=job.job_id, status=job.status, accepted_files=job.total
    )


@router.post(
    "/knowledge/ingest-records",
    response_model=BulkIngestAcceptedResponse,
    status_code=202,
)
async def ingest_knowledge_records(
    file: UploadFile = File(...),
    documentType: DocumentType = Form(...),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> BulkIngestAcceptedResponse:
    """Ingest a multi-equipment record file (JSON or CSV) asynchronously.

    Unlike ``/knowledge/upload`` (one document per equipment), this accepts a
    single tabular dump where every record carries its own ``equipment_id``
    field. Only ``FAILURE_REPORT`` and ``MAINTENANCE_LOG`` document types are
    supported. The file is parsed and validated up front (malformed input is
    rejected with 400); embedding/indexing then runs in the background. Poll
    ``GET /knowledge/bulk-upload/{jobId}`` for progress and counters.
    """
    try:
        job = await service.start_bulk_record_ingest(
            file=file, document_type=documentType.value
        )
    except InvalidRecordFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BulkIngestAcceptedResponse(
        job_id=job.job_id, status=job.status, accepted_files=job.total
    )


@router.get(
    "/knowledge/bulk-upload/{job_id}", response_model=BulkIngestJobStatusResponse
)
async def get_bulk_ingest_job(
    job_id: str,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> BulkIngestJobStatusResponse:
    """Return progress and per-file results for a bulk ingestion job."""
    job = service.get_bulk_job(job_id)
    if job is None:
        raise NotFoundError("Bulk ingestion job not found")

    return BulkIngestJobStatusResponse.model_validate(job)


@router.put("/knowledge/upload/{document_id}", response_model=KnowledgeUploadResponse)
async def replace_knowledge_document(
    document_id: str,
    file: UploadFile = File(...),
    equipmentId: str | None = Form(default=None),
    documentType: DocumentType | None = Form(default=None),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeUploadResponse:
    try:
        updated_id = await service.replace_document(
            document_id=document_id,
            file=file,
            equipment_id=equipmentId,
            document_type=documentType.value if documentType else None,
        )
    except KnowledgeDocumentNotFoundError as exc:
        raise NotFoundError("Knowledge document not found") from exc
    except EquipmentNotFoundError as exc:
        raise NotFoundError("Equipment not found") from exc

    return KnowledgeUploadResponse(document_id=updated_id)


@router.get("/knowledge/{document_id}/chunks", response_model=KnowledgeChunksResponse)
async def get_knowledge_document_chunks(
    document_id: str,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeChunksResponse:
    """Return every chunk stored for a document and the index each lives in."""
    try:
        data = await service.get_document_chunks(document_id)
    except KnowledgeDocumentNotFoundError as exc:
        raise NotFoundError("Knowledge document not found") from exc

    return KnowledgeChunksResponse(**data)


@router.get("/knowledge/{document_id}/download")
async def download_knowledge_document(
    document_id: str,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> FileResponse:
    """Download the original uploaded file for a document."""
    try:
        file_path, file_name = await service.get_document_file(document_id)
    except KnowledgeDocumentNotFoundError as exc:
        raise NotFoundError("Knowledge document not found") from exc

    media_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    return FileResponse(path=file_path, filename=file_name, media_type=media_type)


@router.delete("/knowledge/{document_id}", response_model=KnowledgeDeleteResponse)
async def delete_knowledge_document(
    document_id: str,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeDeleteResponse:
    deleted = await service.delete_document(document_id)
    if not deleted:
        raise NotFoundError("Knowledge document not found")
    return KnowledgeDeleteResponse(status="deleted")
