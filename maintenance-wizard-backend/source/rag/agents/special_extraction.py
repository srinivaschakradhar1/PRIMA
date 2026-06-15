"""Special structured extraction for FAILURE_REPORT and MAINTENANCE_LOG docs.

Failure reports become an Incident Knowledge Base (failure_mode, symptoms,
root_cause, resolution, outcome); maintenance logs become (symptom, action,
result) records. Both are stored separately and embedded into their own indexes
so the search pipeline can perform historical-incident retrieval (design §21-22,
§28).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from rag.llm import llm_client
from rag.models import IncidentRecord, MaintenanceLogRecord

logger = logging.getLogger(__name__)

_SYSTEM = "You are an industrial maintenance knowledge engineer."

_INCIDENT_PROMPT = """Extract every failure incident described in this report.

Document text:
{text}

Return JSON only:
{{"incidents": [{{"failure_mode": "...", "symptoms": ["..."], \
"root_cause": "...", "resolution": "...", "outcome": "..."}}]}}"""

_LOG_PROMPT = """Extract every maintenance event described in this log.

Document text:
{text}

Return JSON only:
{{"entries": [{{"symptom": "...", "action": "...", "result": "..."}}]}}"""


def _excerpt(text: str, limit: int = 8000) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit]


class FailureReportExtractor:
    async def run(
        self, full_text: str, document_id: str, equipment_id: str | None
    ) -> list[IncidentRecord]:
        result = await llm_client.complete_json(
            _SYSTEM, _INCIDENT_PROMPT.format(text=_excerpt(full_text)), max_tokens=1500
        )
        now = datetime.now(timezone.utc)
        records: list[IncidentRecord] = []
        for item in result.get("incidents", []) or []:
            if not isinstance(item, dict):
                continue
            symptoms = item.get("symptoms") or []
            if isinstance(symptoms, str):
                symptoms = [symptoms]
            records.append(
                IncidentRecord(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    equipment_id=equipment_id,
                    failure_mode=str(item.get("failure_mode", "")).strip() or "Unknown",
                    symptoms=[str(s).strip() for s in symptoms if str(s).strip()],
                    root_cause=str(item.get("root_cause", "")).strip(),
                    resolution=str(item.get("resolution", "")).strip(),
                    outcome=str(item.get("outcome", "")).strip(),
                    created_at=now,
                )
            )
        return records


class MaintenanceLogExtractor:
    async def run(
        self, full_text: str, document_id: str, equipment_id: str | None
    ) -> list[MaintenanceLogRecord]:
        result = await llm_client.complete_json(
            _SYSTEM, _LOG_PROMPT.format(text=_excerpt(full_text)), max_tokens=1500
        )
        now = datetime.now(timezone.utc)
        records: list[MaintenanceLogRecord] = []
        for item in result.get("entries", []) or []:
            if not isinstance(item, dict):
                continue
            symptom = str(item.get("symptom", "")).strip()
            action = str(item.get("action", "")).strip()
            if not (symptom or action):
                continue
            records.append(
                MaintenanceLogRecord(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    equipment_id=equipment_id,
                    symptom=symptom,
                    action=action,
                    result=str(item.get("result", "")).strip(),
                    created_at=now,
                )
            )
        return records
