"""Tools available to the conversation and diagnosis agents (_04_Agent.md §13).

These are thin, async, side-effect-light wrappers over the existing repositories
and the RAG vector store. Each agent node calls the tools it needs; the tools
themselves contain no orchestration logic.

The vector-search tools reuse the per-document-type FAISS indexes built by the
ingestion pipeline (``manual_index``, ``sop_index``, ``failure_report_index``,
``maintenance_log_index``, ``spare_part_index``) via the shared
:data:`rag.vectorstore.vector_store`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from models.domain import Equipment
from prediction.engine import analyze_sensor
from rag.agents.intent_detection import DetectedEquipment, EquipmentDetectionAgent
from rag.embeddings import embedding_client
from rag.vectorstore import vector_store
from repositories.agent_repository import AgentMemoryRepository
from repositories.anomaly_alert_repository import AnomalyAlertRepository
from repositories.delay_log_repository import DelayLogRepository
from repositories.equipment_repository import EquipmentRepository
from repositories.fault_message_repository import FaultMessageRepository
from repositories.health_repository import HealthRepository
from repositories.knowledge_repository import KnowledgeRepository
from repositories.rag_repository import RagRepository
from repositories.sensor_reading_repository import SensorReadingRepository
from repositories.spare_part_repository import SparePartRepository
from repositories.time_filters import cutoff

logger = logging.getLogger(__name__)

_SENSOR_HISTORY_DAYS = 7


@dataclass
class ResolvedEquipment:
    """Outcome of the equipment-resolution tool."""

    equipment: DetectedEquipment | None
    match: str | None          # "exact" | "fuzzy" | "context" | None
    confidence: float
    equipment_name: str | None = None


def _parse_ts(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value))
        return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
    except (ValueError, TypeError):
        return None


class MaintenanceTools:
    """Toolbox shared by every agent node.

    Constructed once (repositories are stateless wrappers over the shared
    ``Database`` singleton) and reused across requests.
    """

    def __init__(self, db) -> None:
        self._equipment_repo = EquipmentRepository(db)
        self._reading_repo = SensorReadingRepository(db)
        self._anomaly_repo = AnomalyAlertRepository(db)
        self._fault_repo = FaultMessageRepository(db)
        self._delay_repo = DelayLogRepository(db)
        self._spare_repo = SparePartRepository(db)
        self._health_repo = HealthRepository(db)
        self._memory_repo = AgentMemoryRepository(db)
        self._knowledge_repo = KnowledgeRepository(db)
        self._rag_repo = RagRepository(db)
        self._detector = EquipmentDetectionAgent()
        self._doc_name_cache: dict[str, str] = {}
        self._code_cache: dict[str, str | None] = {}

    # -- equipment-id / code mapping -------------------------------------
    async def _equipment_code(self, equipment_id: str | None) -> str | None:
        """Resolve an internal equipment id (``eq-001``) to its operational
        code (``RMHP-001``).

        The operational tables (sensor_reading, anomaly_alert,
        fault_error_message, equipment_delay_log, spare_parts_inventory) all key
        on the equipment *code*, while the rest of the app uses ``equipment.id``.
        Accepts a code directly (idempotent) so callers can pass either.
        """
        if not equipment_id:
            return None
        if equipment_id in self._code_cache:
            return self._code_cache[equipment_id]
        eq = await self._equipment_repo.get_by_id(equipment_id)
        code = eq.equipment_code if eq else equipment_id  # already a code → passthrough
        self._code_cache[equipment_id] = code
        return code

    # -- equipment -------------------------------------------------------
    async def get_equipment(self, equipment_id: str | None) -> Equipment | None:
        if not equipment_id:
            return None
        return await self._equipment_repo.get_by_id(equipment_id)

    async def list_equipment(self) -> list[Equipment]:
        return await self._equipment_repo.list_all()

    async def resolve_equipment(
        self, message: str, history: list[dict[str, str]]
    ) -> ResolvedEquipment:
        """Resolve the equipment under discussion (_04_Agent.md §6).

        Order: exact/name match in the current message, then a context match
        against the most recent prior turns.
        """
        known = await self._equipment_repo.list_all()
        by_id = {eq.id: eq for eq in known}

        # 1. Current message: exact code match is high-confidence.
        detected = self._detector.run(message, known)
        if detected is not None:
            match = "exact" if self._has_exact_code(message, known) else "fuzzy"
            confidence = 0.95 if match == "exact" else 0.7
            return ResolvedEquipment(detected, match, confidence, self._name(by_id, detected))

        # 2. Context match: scan recent history (most recent first).
        for turn in reversed(history or []):
            content = turn.get("content", "")
            ctx = self._detector.run(content, known)
            if ctx is not None:
                return ResolvedEquipment(ctx, "context", 0.8, self._name(by_id, ctx))

        return ResolvedEquipment(None, None, 0.0)

    @staticmethod
    def _has_exact_code(text: str, known: list[Equipment]) -> bool:
        upper = text.upper()
        return any((eq.equipment_code or "").upper() in upper for eq in known if eq.equipment_code)

    @staticmethod
    def _name(by_id: dict[str, Equipment], det: DetectedEquipment) -> str | None:
        eq = by_id.get(det.equipment_id)
        return eq.equipment_name if eq else None

    # -- sensor history (last 7 days) ------------------------------------
    async def sensor_history(self, equipment_id: str | None) -> dict[str, Any]:
        """Summarise the last 7 days of daily-aggregated readings per channel.

        Channels are analysed with the same :func:`prediction.engine.analyze_sensor`
        logic used by the deterministic engine, off the daily ``status_flag`` plus
        avg/min/max trend (the ``sensor`` threshold table is no longer populated).
        Output shape (``sensors`` + ``breaches``) is unchanged so the diagnosis
        graph keeps working.
        """
        code = await self._equipment_code(equipment_id)
        if not code:
            return {"sensors": [], "breaches": []}

        rows = await self._reading_repo.recent_window(code, days=_SENSOR_HISTORY_DAYS)
        if not rows:
            return {"sensors": [], "breaches": []}

        grouped: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            name = r.get("sensor_name")
            if name:
                grouped.setdefault(name, []).append(r)

        summary: list[dict[str, Any]] = []
        breaches: list[dict[str, Any]] = []
        for name, channel_rows in grouped.items():
            a = analyze_sensor(name, channel_rows)
            if a is None:
                continue
            entry = {
                "sensor_code": a.sensor_name,
                "sensor_type": a.sensor_type,
                "unit": None,
                "count": a.count,
                "min": a.minimum,
                "max": a.maximum,
                "avg": a.mean,
                "latest": a.latest_value,
                "status": a.status,
                "pct_warning": a.pct_warning,
                "pct_critical": a.pct_critical,
            }
            summary.append(entry)
            if a.status in ("CRITICAL", "WARNING"):
                breaches.append({
                    "sensor_code": a.sensor_name,
                    "status": a.status,
                    "latest": a.latest_value,
                    "max": a.maximum,
                    "unit": None,
                })
        return {"sensors": summary, "breaches": breaches}

    # -- equipment health ------------------------------------------------
    async def equipment_health(self, equipment_id: str | None) -> dict[str, Any] | None:
        if not equipment_id:
            return None
        record = await self._health_repo.get_latest_active(equipment_id)
        if record is None:
            return None
        actions: list[str] = []
        if record.preventive_actions_json:
            try:
                parsed = json.loads(record.preventive_actions_json)
                if isinstance(parsed, list):
                    actions = [
                        a.get("action") if isinstance(a, dict) else str(a) for a in parsed
                    ]
                elif isinstance(parsed, dict):
                    actions = [str(v) for v in parsed.values()]
            except (ValueError, TypeError):
                pass
        return {
            "health_score": record.health_score,
            "risk_level": record.risk_level,
            "rul_days": record.rul_days,
            "failure_probability": record.failure_probability,
            "predicted_failure": record.predicted_failure,
            "preventive_actions": [a for a in actions if a],
        }

    # -- operational-data tools (SQL over the time-series tables) --------
    async def get_sensor_reading(
        self,
        equipment_id: str | None,
        start_date: str | None = None,
        end_date: str | None = None,
        days: float = 5.0,
    ) -> dict[str, Any]:
        """Daily-aggregated sensor readings for an equipment as a markdown table.

        If ``start_date``/``end_date`` (``YYYY-MM-DD``) are omitted, returns the
        last ``days`` days. Returns both a ``markdown`` rendering (for the LLM to
        see exactly which days each channel was abnormal) and the raw ``rows``.
        """
        code = await self._equipment_code(equipment_id)
        if not code:
            return {"markdown": "", "rows": []}
        if start_date is None and end_date is None:
            rows = await self._reading_repo.recent_window(code, days=days)
        else:
            rows = await self._reading_repo.list_by_equipment(code, start_date, end_date)
        cols = ["date", "sensor_name", "avg_value", "min_value", "max_value", "std_dev", "status_flag"]
        return {"markdown": self._markdown_table(rows, cols), "rows": rows}

    async def get_anomaly_alert(
        self,
        equipment_id: str | None,
        sensor_name: str | None = None,
        min_deviation_pct: float | None = None,
        before: str | None = None,
        number_of_records: int = 20,
        hours: float | None = None,
    ) -> dict[str, Any]:
        """Anomaly alerts for an equipment, newest first, as a markdown table.

        Optional filters mirror the alert schema: ``sensor_name``, deviation
        strictly greater than ``min_deviation_pct``, and ``before`` (timestamp
        strictly earlier than). ``hours`` restricts to a recent window (e.g. 24).
        """
        code = await self._equipment_code(equipment_id)
        if not code:
            return {"markdown": "", "rows": []}
        rows = await self._anomaly_repo.list_for_equipment(
            code,
            since=cutoff(hours / 24.0) if hours else None,
            before=_parse_ts(before) if before else None,
            sensor_name=sensor_name,
            min_deviation_pct=min_deviation_pct,
            limit=number_of_records,
        )
        cols = ["timestamp", "sensor_name", "observed_value", "baseline_value",
                "deviation_pct", "alert_level", "probable_cause", "resolution_status"]
        return {"markdown": self._markdown_table(rows, cols), "rows": rows}

    async def get_fault_error_messages(
        self,
        equipment_id: str | None,
        hours: float = 24.0,
        message_type: str | None = None,
        number_of_records: int = 30,
    ) -> dict[str, Any]:
        """SCADA/PLC fault & alarm messages in the last ``hours`` as markdown."""
        code = await self._equipment_code(equipment_id)
        if not code:
            return {"markdown": "", "rows": []}
        rows = await self._fault_repo.list_for_equipment(
            code, since=cutoff(hours / 24.0), message_type=message_type, limit=number_of_records
        )
        cols = ["timestamp", "fault_code", "message_type", "message_text", "source_system"]
        return {"markdown": self._markdown_table(rows, cols), "rows": rows}

    async def get_equipment_delay_log(
        self,
        equipment_id: str | None,
        hours: float = 24.0,
        number_of_records: int = 30,
    ) -> dict[str, Any]:
        """Production delay / breakdown entries in the last ``hours`` as markdown."""
        code = await self._equipment_code(equipment_id)
        if not code:
            return {"markdown": "", "rows": []}
        rows = await self._delay_repo.list_for_equipment(
            code, since=cutoff(hours / 24.0), limit=number_of_records
        )
        cols = ["timestamp", "shift", "delay_type", "cause_description",
                "duration_minutes", "severity", "production_loss_tonnes"]
        return {"markdown": self._markdown_table(rows, cols), "rows": rows}

    async def get_spare_parts(
        self,
        equipment_id: str | None,
        part_query: str | None = None,
        number_of_records: int = 50,
    ) -> dict[str, Any]:
        """Spare-parts inventory for an equipment (scarce parts first) as markdown."""
        code = await self._equipment_code(equipment_id)
        if not code:
            return {"markdown": "", "rows": []}
        rows = await self._spare_repo.list_for_equipment(
            code, part_query=part_query, limit=number_of_records
        )
        cols = ["part_name", "current_stock", "reorder_point", "stock_status",
                "procurement_lead_time_days", "preferred_vendor", "criticality"]
        return {"markdown": self._markdown_table(rows, cols), "rows": rows}

    @staticmethod
    def _markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
        """Render rows as a GitHub-flavoured markdown table (empty string if none)."""
        if not rows:
            return ""
        header = "| " + " | ".join(columns) + " |"
        sep = "| " + " | ".join("---" for _ in columns) + " |"
        lines = [header, sep]
        for row in rows:
            cells = []
            for c in columns:
                v = row.get(c)
                cells.append("" if v is None else str(v).replace("|", "\\|"))
            lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines)

    # -- vector search tools ---------------------------------------------
    async def search_index(
        self,
        index_name: str,
        query: str,
        equipment_id: str | None,
        k: int = 5,
    ) -> list[dict[str, Any]]:
        """Hybrid (dense + BM25 lexical) search of one named vector index,
        strictly scoped to the equipment under discussion.

        Uses the same RRF-fused dense+sparse retrieval as the chat search
        pipeline so the diagnosis agent's per-hypothesis evidence is gathered with
        the same rigour.

        Retrieval is restricted **at the vector-store level** to embeddings whose
        payload ``equipment_id`` matches the requested one (see
        :meth:`rag.vectorstore.VectorIndex.hybrid_search`). Cross-equipment
        evidence is never returned: a hypothesis is never "supported" by an
        unrelated asset's history — better to return fewer, on-target results (or
        none) than misleading ones. When ``equipment_id`` is unknown the search
        runs unrestricted.
        """
        if not query.strip():
            return []
        qv = await embedding_client.embed_one(query)
        # Over-fetch so ref_id dedup still leaves useful results.
        hits = vector_store.hybrid_search(
            [index_name], qv, query, max(k * 3, k), equipment_id=equipment_id
        )

        # Records ingested from tabular dumps emit several vectors that share a
        # ``ref_id`` (e.g. a failure report's symptom / description / root-cause
        # facets). Collapse them to the first (highest-ranked) hit so a single
        # source record yields a single piece of evidence.
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for hit in hits:
            ref = hit.ref_id
            if ref and ref in seen:
                continue
            payload = hit.payload
            result.append(self._hit_to_row(index_name, hit, payload, payload.get("equipment_id")))
            if ref:
                seen.add(ref)
        return result[:k]

    @staticmethod
    def _hit_to_row(
        index_name: str, hit, payload: dict[str, Any], eid: str | None
    ) -> dict[str, Any]:
        # Blend dense + lexical into a single score so downstream evidence
        # weighting reflects exact code / part-number matches too.
        score = 0.7 * float(hit.semantic_score) + 0.3 * float(hit.lexical_score)
        return {
            "type": hit.kind,
            "index": index_name,
            "score": round(score, 4),
            "text": payload.get("text", ""),
            "concept": payload.get("concept"),
            "document_id": payload.get("document_id"),
            "record_key": payload.get("record_key"),
            "event_date": payload.get("event_date"),
            "page": payload.get("page"),
            "equipment_id": eid,
            "equipment_type": payload.get("equipment_type"),
            "failure_mode": payload.get("failure_mode"),
            "root_cause": payload.get("root_cause"),
            "resolution": payload.get("resolution"),
            "symptom": payload.get("symptom"),
            "action": payload.get("action"),
            "result": payload.get("result"),
        }

    async def search_incidents(
        self, query: str, equipment_id: str | None, k: int = 5
    ) -> list[dict[str, Any]]:
        return await self.search_index(
            "failure_report_index", query, equipment_id, k
        )

    async def search_maintenance_logs(
        self, query: str, equipment_id: str | None, k: int = 5
    ) -> list[dict[str, Any]]:
        return await self.search_index(
            "maintenance_log_index", query, equipment_id, k
        )

    async def search_manual(
        self, query: str, equipment_id: str | None, k: int = 5
    ) -> list[dict[str, Any]]:
        return await self.search_index("manual_index", query, equipment_id, k)

    async def search_sop(
        self, query: str, equipment_id: str | None, k: int = 5
    ) -> list[dict[str, Any]]:
        return await self.search_index("sop_index", query, equipment_id, k)

    # -- episodic memory (memory-assisted hypotheses, _04_Agent.md §15) --
    async def episodic_memory(
        self, equipment_id: str | None
    ) -> list[dict[str, Any]]:
        """Return prior validated diagnoses for this equipment from agent_memory."""
        if not equipment_id:
            return []
        from models.enums import InteractionType

        memories = await self._memory_repo.list_by_equipment(equipment_id)
        hits: list[dict[str, Any]] = []
        for m in memories:
            if m.interaction_type != InteractionType.DIAGNOSIS.value:
                continue
            hits.append({
                "symptoms": m.user_query or "",
                "diagnosis": m.agent_response or "",
                "outcome": m.outcome,
            })
        return hits[:10]

    # -- historical symptoms (co-occurring-symptom enrichment) -----------
    async def historical_symptom_groups(
        self, equipment_id: str | None
    ) -> list[list[str]]:
        """Past-incident symptom sets for an equipment, grouped by incident.

        Each inner list is the set of symptoms recorded *together* in one past
        failure report, so the conversation agent can reason about which symptoms
        historically co-occur with the ones the engineer reported (rather than
        treating every recorded symptom as an undifferentiated pool). Intra-group
        duplicates are collapsed and only groups with at least two distinct
        symptoms are kept, since a lone symptom carries no co-occurrence signal.

        The structured table may be keyed by either the equipment *code* or the
        internal id depending on ingestion, so if the value passed yields nothing
        we retry with the resolved code.
        """
        if not equipment_id:
            return []
        groups = await self._rag_repo.list_incident_symptom_groups(equipment_id)
        if not groups:
            code = await self._equipment_code(equipment_id)
            if code and code != equipment_id:
                groups = await self._rag_repo.list_incident_symptom_groups(code)
        out: list[list[str]] = []
        for group in groups:
            deduped = self._dedupe_ci(group)
            if len(deduped) >= 2:
                out.append(deduped)
        return out

    @staticmethod
    def _dedupe_ci(items: list[str]) -> list[str]:
        """De-duplicate case-insensitively, preserving first-seen order."""
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            norm = " ".join(item.split())
            key = norm.lower()
            if norm and key not in seen:
                seen.add(key)
                out.append(norm)
        return out

    # -- citations -------------------------------------------------------
    async def doc_name(self, document_id: str | None) -> str:
        """Resolve a document id to its human-readable name (cached)."""
        if not document_id:
            return "unknown"
        if document_id in self._doc_name_cache:
            return self._doc_name_cache[document_id]
        doc = await self._knowledge_repo.get_by_id(document_id)
        name = doc.document_name if doc and doc.document_name else document_id
        self._doc_name_cache[document_id] = name
        return name
