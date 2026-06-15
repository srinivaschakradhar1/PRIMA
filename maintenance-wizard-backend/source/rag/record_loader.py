"""Loader and chunk builders for bulk structured-record ingestion.

Some knowledge sources are *plant-wide tabular dumps* — one file holding many
records that each belong to a different equipment (e.g. a failure-analysis
report export or a maintenance-history sheet) — rather than a single document
about one equipment. Every record carries a mandatory ``equipment_id``.

Because the data is already structured, this module bypasses the LLM extraction
pipeline (``rag.ingestion``'s parse -> merge -> concept/relationship -> chunk
boundary -> LLM special-extraction). Instead it maps fields directly:

* the high-signal free-text is embedded (failure reports embed three facet views
  per record — symptoms, failure description, root cause — to widen recall);
* the *full rendered record* is stored as the vector payload so corrective
  actions ride along and surface on retrieval;
* the real **event date** (failure / maintenance date) is stamped as
  ``created_at`` (driving the recency ranking) and ``event_date``;
* a structured :class:`IncidentRecord` / :class:`MaintenanceLogRecord` row is
  produced for the relational knowledge base.

The builders are pure (no I/O); equipment validation and indexing happen in
:class:`rag.ingestion.IngestionPipeline`.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from models.domain import Equipment
from rag.models import IncidentRecord, MaintenanceLogRecord
from repositories.equipment_repository import EquipmentRepository

# Keep only the most recent N maintenance records per equipment (older history
# adds little diagnostic value and would balloon the embedding count).
MAINTENANCE_RECORDS_PER_EQUIPMENT = 10


class RecordParseError(ValueError):
    """Raised when an uploaded record file cannot be parsed or is malformed."""


@dataclass
class BuildResult:
    """Output of a chunk builder: embeddable entries + structured rows + stats.

    ``entries`` pairs the text to embed with the vector payload to store. The
    embed text differs per facet; the payload (``text`` field) is the full record.
    """

    entries: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    incidents: list[IncidentRecord] = field(default_factory=list)
    logs: list[MaintenanceLogRecord] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def load_records(raw: bytes, filename: str | None, document_type: str) -> list[dict[str, Any]]:
    """Parse a JSON or CSV byte payload into a list of record dicts.

    Validates that every record carries a non-empty ``equipment_id`` (the field
    used to attribute each record to its equipment).
    """
    name = (filename or "").lower()
    if name.endswith(".json"):
        records = _load_json(raw)
    elif name.endswith(".csv"):
        records = _load_csv(raw)
    else:
        raise RecordParseError(
            "Unsupported file type; expected a .json or .csv file."
        )

    if not records:
        raise RecordParseError("File contains no records.")

    for idx, rec in enumerate(records):
        if not str(rec.get("equipment_id") or "").strip():
            raise RecordParseError(
                f"Record at position {idx} is missing the required 'equipment_id' field."
            )
    return records


def _load_json(raw: bytes) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecordParseError(f"Invalid JSON: {exc}") from exc
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        # Tolerate a wrapper object holding the records under a single list key.
        for value in data.values():
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
    raise RecordParseError("JSON must be a list of record objects.")


def _load_csv(raw: bytes) -> list[dict[str, Any]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RecordParseError(f"Invalid CSV encoding: {exc}") from exc
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


# ---------------------------------------------------------------------------
# Failure-report builder (FAILURE_REPORT)
# ---------------------------------------------------------------------------
def build_failure_chunks(
    records: list[dict[str, Any]],
    document_id: str,
    equipment_repo: EquipmentRepository,
) -> BuildResult:
    """Build 3 facet vectors + 1 IncidentRecord per failure-analysis report.

    The three facet embeddings (symptoms / failure description / root cause) all
    share the same ``ref_id`` and full-record payload, so the retriever can
    dedupe them back to a single hit while still benefiting from the wider recall.
    """
    result = BuildResult()
    skipped_unknown = 0

    for rec in records:
        eid = str(rec.get("equipment_id") or "").strip()
        equipment: Equipment | None = equipment_repo.get_by_code_sync(eid)

        if not equipment:
            skipped_unknown += 1
            continue

        event_dt = _parse_date(rec.get("date_of_failure")) or _parse_date(rec.get("report_date"))
        created_at_iso = (event_dt or datetime.now(timezone.utc)).isoformat()
        event_date = event_dt.date().isoformat() if event_dt else None

        symptoms = _as_list(rec.get("symptoms_observed"))
        rca = rec.get("root_cause_analysis") or {}
        identified = str(rca.get("identified_root_cause") or "").strip()
        five_why = _as_list(rca.get("five_why_chain"))
        contributing = _as_list(rca.get("contributing_factors"))
        corrective = rec.get("corrective_actions") or {}
        immediate = str(corrective.get("immediate") or "").strip()
        long_term = str(corrective.get("long_term") or "").strip()

        incident_id = str(uuid.uuid4())
        record_key = str(rec.get("report_id") or incident_id)
        resolution = _join_actions(immediate, long_term)
        root_cause = " ".join(five_why) if five_why else identified
        full_text = _render_failure_text(
            rec, symptoms, identified, five_why, contributing, immediate, long_term
        )

        result.incidents.append(
            IncidentRecord(
                id=incident_id,
                document_id=document_id,
                equipment_id=equipment.id,
                failure_mode=identified or str(rec.get("title") or "Unknown failure"),
                symptoms=symptoms,
                root_cause=root_cause,
                resolution=resolution,
                outcome=str(rec.get("status") or ""),
                created_at=event_dt,
            )
        )

        base_payload: dict[str, Any] = {
            "kind": "incident",
            "ref_id": incident_id,  # shared across facets -> retrieval dedup
            "record_key": record_key,
            "document_id": document_id,
            "equipment_id": equipment.id,
            "equipment_type": equipment.equipment_type,
            "document_type": "FAILURE_REPORT",
            "concept": identified or None,
            "semantic_type": "FAILURE_MODE",
            "failure_mode": identified,
            "root_cause": root_cause,
            "resolution": resolution,
            "outcome": str(rec.get("status") or ""),
            "page": 1,
            "text": full_text,
            "event_date": event_date,
            "created_at": created_at_iso,
        }

        facets = (
            ("SYMPTOMS", "Symptoms: " + ("; ".join(symptoms) if symptoms else "n/a")),
            ("FAILURE_DESCRIPTION", str(rec.get("failure_description") or "").strip()),
            ("ROOT_CAUSE", _facet_root_cause(identified, five_why, contributing)),
        )
        for facet_type, facet_text in facets:
            if not facet_text.strip():
                continue
            payload = dict(base_payload)
            payload["facet"] = facet_type
            result.entries.append((facet_text, payload))

    result.stats = {
        "records": len(records),
        "incidents": len(result.incidents),
        "embeddings": len(result.entries),
        "skipped_unknown": skipped_unknown,
        "skipped_na": 0,
    }
    return result


# ---------------------------------------------------------------------------
# Maintenance-history builder (MAINTENANCE_LOG)
# ---------------------------------------------------------------------------
def build_maintenance_chunks(
    records: list[dict[str, Any]],
    document_id: str,
    equipment_repo: EquipmentRepository,
) -> BuildResult:
    """Build 1 vector + 1 MaintenanceLogRecord per kept maintenance row.

    Routine ``N/A`` rows are dropped, then only the latest
    ``MAINTENANCE_RECORDS_PER_EQUIPMENT`` records per equipment (by maintenance
    date) are embedded and stored.
    """
    result = BuildResult()
    skipped_unknown = 0
    skipped_na = 0
    by_equipment: dict[str, list[dict[str, Any]]] = defaultdict(list)
    type_by_id: dict[str, str | None] = {}

    for rec in records:
        eid = str(rec.get("equipment_id") or "").strip()
        equipment: Equipment | None = equipment_repo.get_by_code_sync(eid)

        if not equipment:
            skipped_unknown += 1
            continue

        if _is_routine_na(rec):
            skipped_na += 1
            continue
        by_equipment[equipment.id].append(rec)
        type_by_id[equipment.id] = equipment.equipment_type

    _epoch = datetime.min.replace(tzinfo=timezone.utc)
    for eid, recs in by_equipment.items():
        recs.sort(
            key=lambda r: _parse_date(r.get("maintenance_date")) or _epoch,
            reverse=True,
        )
        for rec in recs[:MAINTENANCE_RECORDS_PER_EQUIPMENT]:
            event_dt = _parse_date(rec.get("maintenance_date"))
            created_at_iso = (event_dt or datetime.now(timezone.utc)).isoformat()
            event_date = event_dt.date().isoformat() if event_dt else None

            mtype = str(rec.get("maintenance_type") or "").strip()
            failure_mode = str(rec.get("failure_mode_addressed") or "").strip()
            root_cause = str(rec.get("root_cause") or "").strip()
            action = str(rec.get("corrective_action") or "").strip()
            parts = str(rec.get("parts_replaced") or "").strip()

            log_id = str(uuid.uuid4())
            record_key = str(rec.get("record_id") or log_id)
            result_text = _maintenance_result(parts, mtype)
            embed_text = (
                f"Maintenance type: {mtype}. Failure mode: {failure_mode}. "
                f"Root cause: {root_cause}. Action: {action}. Parts replaced: {parts}."
            )
            full_text = _render_maintenance_text(rec)

            result.logs.append(
                MaintenanceLogRecord(
                    id=log_id,
                    document_id=document_id,
                    equipment_id=eid,
                    symptom=failure_mode,
                    action=action,
                    result=result_text,
                    created_at=event_dt,
                )
            )
            payload: dict[str, Any] = {
                "kind": "maintenance_log",
                "ref_id": log_id,
                "record_key": record_key,
                "document_id": document_id,
                "equipment_id": eid,
                "equipment_type": type_by_id.get(eid),
                "document_type": "MAINTENANCE_LOG",
                "concept": failure_mode or None,
                "semantic_type": "MAINTENANCE_TASK",
                "symptom": failure_mode,
                "action": action,
                "result": result_text,
                "page": 1,
                "text": full_text,
                "event_date": event_date,
                "created_at": created_at_iso,
            }
            result.entries.append((embed_text, payload))

    result.stats = {
        "records": len(records),
        "maintenance_logs": len(result.logs),
        "embeddings": len(result.entries),
        "skipped_unknown": skipped_unknown,
        "skipped_na": skipped_na,
    }
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _is_routine_na(rec: dict[str, Any]) -> bool:
    """True when a maintenance row addressed no actual failure (skip it).

    Scheduled preventive rows carry ``N/A`` for both the failure mode and the
    root cause (their ``corrective_action`` is a routine task such as "Bolt
    torque check", so it is not part of the test). These carry little signal for
    proactive failure detection, so they are dropped before the latest-N cut.
    """
    return _is_na(rec.get("failure_mode_addressed")) and _is_na(rec.get("root_cause"))


def _is_na(value: Any) -> bool:
    text = str(value or "").strip().upper()
    return not text or text.startswith("N/A")


def _as_list(value: Any) -> list[str]:
    """Normalise a field that may be a list, a delimited string, or empty."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    if not text:
        return []
    # CSV/string fields sometimes pack multiple values with ; or |.
    for sep in (";", "|"):
        if sep in text:
            return [p.strip() for p in text.split(sep) if p.strip()]
    return [text]


def _join_actions(immediate: str, long_term: str) -> str:
    parts = []
    if immediate:
        parts.append(f"Immediate: {immediate}")
    if long_term:
        parts.append(f"Long-term: {long_term}")
    return " ".join(parts)


def _facet_root_cause(identified: str, five_why: list[str], contributing: list[str]) -> str:
    pieces = []
    if identified:
        pieces.append(f"Root cause: {identified}")
    if five_why:
        pieces.append("Five-why: " + " ".join(five_why))
    if contributing:
        pieces.append("Contributing factors: " + ", ".join(contributing))
    return ". ".join(pieces)


def _maintenance_result(parts: str, mtype: str) -> str:
    if parts and mtype:
        return f"{parts} ({mtype})"
    return parts or mtype


def _parse_date(value: Any) -> datetime | None:
    """Parse an ISO date/datetime string into a UTC-aware datetime."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _render_failure_text(
    rec: dict[str, Any],
    symptoms: list[str],
    identified: str,
    five_why: list[str],
    contributing: list[str],
    immediate: str,
    long_term: str,
) -> str:
    """Render a full failure report into the text stored against every facet vector."""
    lines = [
        str(rec.get("title") or "Failure Analysis Report").strip(),
        f"Equipment: {rec.get('equipment_name') or ''} ({rec.get('equipment_id') or ''}).",
        f"Date of failure: {rec.get('date_of_failure') or 'unknown'}.",
    ]
    if rec.get("failure_description"):
        lines.append(f"Failure description: {rec['failure_description']}")
    if symptoms:
        lines.append("Symptoms observed: " + "; ".join(symptoms) + ".")
    if identified:
        lines.append(f"Identified root cause: {identified}.")
    if five_why:
        lines.append("Five-why analysis: " + " ".join(five_why))
    if contributing:
        lines.append("Contributing factors: " + ", ".join(contributing) + ".")
    actions = _join_actions(immediate, long_term)
    if actions:
        lines.append(f"Corrective actions: {actions}.")
    if rec.get("status"):
        lines.append(f"Status: {rec['status']}.")
    return "\n".join(line for line in lines if line)


def _render_maintenance_text(rec: dict[str, Any]) -> str:
    """Render a full maintenance record into the stored vector payload text."""
    lines = [
        f"Maintenance record for {rec.get('equipment_name') or ''} "
        f"({rec.get('equipment_id') or ''}) on {rec.get('maintenance_date') or 'unknown'}.",
        f"Type: {rec.get('maintenance_type') or 'unknown'}.",
    ]
    if rec.get("failure_mode_addressed"):
        lines.append(f"Failure mode addressed: {rec['failure_mode_addressed']}.")
    if rec.get("root_cause"):
        lines.append(f"Root cause: {rec['root_cause']}.")
    if rec.get("corrective_action"):
        lines.append(f"Corrective action: {rec['corrective_action']}.")
    if rec.get("parts_replaced"):
        lines.append(f"Parts replaced: {rec['parts_replaced']}.")
    if rec.get("technician"):
        lines.append(f"Technician: {rec['technician']}.")
    if rec.get("work_order_no"):
        lines.append(f"Work order: {rec['work_order_no']}.")
    return "\n".join(line for line in lines if line)
