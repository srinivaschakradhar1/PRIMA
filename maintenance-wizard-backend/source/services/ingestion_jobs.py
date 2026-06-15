"""In-memory tracking for asynchronous bulk ingestion jobs.

A bulk folder ingestion runs as an ``asyncio`` background task after the API has
already acknowledged the request. The job state therefore cannot live on the
request-scoped ``KnowledgeService`` instance (a fresh one is built per request by
``get_knowledge_service``); it lives in this module-level ``job_store`` singleton
so the status endpoint can read progress on subsequent requests.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FileResult:
    """Outcome of ingesting a single file within a bulk job."""

    file_name: str
    equipment_id: str | None
    document_id: str | None
    status: str  # "succeeded" | "failed"
    error: str | None = None


@dataclass
class BulkIngestJob:
    """Progress and per-file results for one bulk folder ingestion.

    The same structure tracks single-file *record* ingestion (a tabular dump of
    many records spanning many equipment). There ``total``/``processed`` count
    records rather than files and the record-level counters below are populated;
    ``folder_path`` holds the uploaded file name.
    """

    job_id: str
    status: str  # "queued" | "running" | "completed"
    folder_path: str
    document_type: str
    total: int
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    results: list[FileResult] = field(default_factory=list)
    # Record-ingestion counters (0 for file/folder jobs).
    embeddings: int = 0
    indexed_records: int = 0
    skipped_na: int = 0
    skipped_unknown_equipment: int = 0


class BulkIngestJobStore:
    """Module-level registry of bulk ingestion jobs and their running tasks.

    The store keeps a hard reference to each background ``asyncio.Task`` so it is
    not garbage-collected mid-run (``asyncio.create_task`` only holds a weak
    reference). The reference is dropped via a done-callback once the task ends.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, BulkIngestJob] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def create(self, folder_path: str, document_type: str, total: int) -> BulkIngestJob:
        job_id = str(uuid.uuid4())
        job = BulkIngestJob(
            job_id=job_id,
            status="queued",
            folder_path=folder_path,
            document_type=document_type,
            total=total,
        )
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> BulkIngestJob | None:
        return self._jobs.get(job_id)

    def attach_task(self, job_id: str, task: asyncio.Task) -> None:
        self._tasks[job_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(job_id, None))


# Single shared instance used across the application.
job_store = BulkIngestJobStore()
