"""Agentic equipment-health refresh job.

A three-stage periodic pipeline that supersedes the purely deterministic
``HealthPredictionService`` for the scheduled job:

1. **Deterministic triage (cheap, every equipment).** Compute the health score /
   risk / RUL from :mod:`prediction.engine` over the daily-aggregated sensor
   history, and gather recency signals (anomaly alerts, fault messages and delay
   logs from the last 24h). Decide whether the equipment is *suspect*.
2. **Agentic deep analysis (suspect equipment only).** Invoke the multi-step
   :class:`~agents.diagnosis.DiagnosisAgent`, which consolidates sensor / anomaly
   / fault / delay / incident / maintenance / manual evidence into an
   explainable, source-cited report (diagnosis, root cause, corrective actions,
   spare parts and a days-to-shutdown estimate).
3. **Persist.** Write one ``equipment_health_record`` carrying the deterministic
   score/risk/RUL plus the agent report JSON, superseding the prior active row.

After the per-equipment loop a plant-level **bottleneck ranking** orders the
suspect equipment by process criticality, delay severity and spares constraints.

The deterministic score is always the source of truth; the agent narrative is
advisory and stored separately. OpenAI failures are isolated per equipment and
fall back to a deterministic-only record so one bad call never aborts the batch.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from agents.diagnosis import DiagnosisAgent
from agents.tools import MaintenanceTools
from models.domain import Equipment, EquipmentHealthRecord
from prediction.engine import HealthPrediction, predict_health
from repositories.equipment_repository import EquipmentRepository
from repositories.health_repository import HealthRepository
from repositories.sensor_reading_repository import SensorReadingRepository
from repositories.time_filters import cutoff

logger = logging.getLogger(__name__)

_HEALTH_WINDOW_DAYS = 30.0
_TRIAGE_WINDOW_HOURS = 24.0

_RISK_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
_CRIT_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
_SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


class AgenticHealthService:
    """Computes, optionally deep-analyses, and persists equipment health."""

    def __init__(self, db) -> None:
        self._db = db
        self._equipment_repo = EquipmentRepository(db)
        self._reading_repo = SensorReadingRepository(db)
        self._health_repo = HealthRepository(db)
        self._tools = MaintenanceTools(db)
        self._diagnosis = DiagnosisAgent(self._tools)

    # -- public API ------------------------------------------------------
    async def refresh_all(self, now: datetime | None = None) -> dict[str, Any]:
        """Refresh every equipment; deep-analyse suspects; rank the bottlenecks."""
        now = now or datetime.now(timezone.utc)
        await self._health_repo.ensure_columns()
        equipment = await self._equipment_repo.list_all()

        results: list[dict[str, Any]] = []
        analysed = 0
        for eq in equipment:
            try:
                summary = await self._refresh_one(eq, now)
            except Exception:  # one bad equipment must not abort the batch
                logger.exception("Health refresh failed for equipment %s", eq.id)
                continue
            if summary is None:
                continue
            analysed += 1 if summary.get("agent_analysed") else 0
            results.append(summary)

        ranking = self._bottleneck_ranking(results)
        suspects = [r for r in results if r.get("suspect")]
        logger.info(
            "Agentic health refresh complete: %d equipment, %d suspect, %d deep-analysed.",
            len(results), len(suspects), analysed,
        )
        return {
            "refreshed": len(results),
            "suspect": len(suspects),
            "deep_analysed": analysed,
            "generated_at": now.isoformat(),
            "bottleneck_ranking": ranking,
            "equipment": results,
        }

    async def refresh_one(
        self, equipment_id: str, now: datetime | None = None
    ) -> dict[str, Any] | None:
        """Refresh a single equipment (used by the manual endpoint)."""
        now = now or datetime.now(timezone.utc)
        await self._health_repo.ensure_columns()
        eq = await self._equipment_repo.get_by_id(equipment_id)
        if eq is None:
            return None
        return await self._refresh_one(eq, now)

    # -- per-equipment pipeline ------------------------------------------
    async def _refresh_one(self, eq: Equipment, now: datetime) -> dict[str, Any] | None:
        # The equipment *code* is the canonical key across the app and the
        # operational tables (sensor_reading, anomaly_alert, ...); health records
        # are persisted under it too so every health/report endpoint resolves.
        key = eq.equipment_code or eq.id

        # Stage 1 — deterministic prediction.
        start = cutoff(_HEALTH_WINDOW_DAYS).strftime("%Y-%m-%d")
        readings = await self._reading_repo.list_by_equipment(key, start_date=start) if key else []
        prediction = predict_health(eq, readings, now=now)

        # Stage 1 — recency / triage signals (last 24h).
        triage = await self._triage_signals(key)
        suspect = self._is_suspect(eq, prediction, triage)

        # Stage 2 — agentic deep analysis for suspect equipment only.
        report: dict[str, Any] | None = None
        if suspect:
            try:
                report = await self._run_agent(eq, key, prediction, triage)
            except Exception:
                logger.exception("Agent diagnosis failed for %s; storing deterministic record", key)
                report = None

        # Stage 3 — persist (keyed by the canonical code).
        await self._persist(key, eq, prediction, report, now)

        return {
            "equipment_id": key,
            "equipment_code": eq.equipment_code,
            "criticality": eq.criticality,
            "status": eq.status,
            "health_score": prediction.health_score,
            "risk_level": prediction.risk_level,
            "rul_days": prediction.rul_days,
            "failure_probability": prediction.failure_probability,
            "predicted_failure": (report or {}).get("diagnosis") or prediction.predicted_failure,
            "suspect": suspect,
            "agent_analysed": report is not None,
            "triage": triage,
            "report": report,
        }

    async def _triage_signals(self, eid: str) -> dict[str, Any]:
        """Recent operational signals used both for gating and ranking."""
        anomalies = (await self._tools.get_anomaly_alert(eid, number_of_records=50, hours=_TRIAGE_WINDOW_HOURS)).get("rows", [])
        faults = (await self._tools.get_fault_error_messages(eid, hours=_TRIAGE_WINDOW_HOURS, number_of_records=50)).get("rows", [])
        delays = (await self._tools.get_equipment_delay_log(eid, hours=_TRIAGE_WINDOW_HOURS, number_of_records=50)).get("rows", [])
        spares = (await self._tools.get_spare_parts(eid, number_of_records=50)).get("rows", [])

        crit_anomaly = any(str(a.get("alert_level") or "").lower() == "critical" for a in anomalies)
        severe_fault = any(str(f.get("message_type") or "").lower() in ("trip", "fault") for f in faults)
        max_delay_sev = max(
            (_SEVERITY_RANK.get(str(d.get("severity") or "").upper(), 0) for d in delays),
            default=0,
        )
        scarce_spares = sum(
            1 for s in spares if str(s.get("stock_status") or "").lower() in ("out of stock", "reorder required")
        )
        min_lead = min(
            (s.get("procurement_lead_time_days") for s in spares
             if isinstance(s.get("procurement_lead_time_days"), (int, float))),
            default=None,
        )
        return {
            "anomalies_24h": len(anomalies),
            "critical_anomaly": crit_anomaly,
            "faults_24h": len(faults),
            "severe_fault": severe_fault,
            "delays_24h": len(delays),
            "max_delay_severity": max_delay_sev,
            "scarce_spares": scarce_spares,
            "min_spare_lead_days": min_lead,
        }

    @staticmethod
    def _is_suspect(eq: Equipment, prediction: HealthPrediction, triage: dict[str, Any]) -> bool:
        if (eq.status or "").upper() == "FAILED":
            return True
        if _RISK_RANK.get((prediction.risk_level or "").upper(), 0) >= _RISK_RANK["MEDIUM"]:
            return True
        if prediction.abnormal_symptoms:
            return True
        if triage.get("critical_anomaly") or triage.get("severe_fault"):
            return True
        if triage.get("max_delay_severity", 0) >= _SEVERITY_RANK["HIGH"]:
            return True
        return False

    async def _run_agent(
        self, eq: Equipment, key: str, prediction: HealthPrediction, triage: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke the diagnosis graph and shape its output into a report."""
        symptoms = list(prediction.abnormal_symptoms)
        if not symptoms:
            symptoms = [f"{triage.get('anomalies_24h', 0)} anomaly alerts and "
                        f"{triage.get('faults_24h', 0)} fault messages in last 24h"]
        question = (
            f"Assess the health of {eq.equipment_code} ({eq.equipment_type}). "
            f"Deterministic risk {prediction.risk_level}, health {prediction.health_score}, "
            f"RUL {prediction.rul_days}d. Determine whether it is faulty and, if so, the root "
            "cause, corrective actions, spare parts and days to shutdown."
        )
        result = await self._diagnosis.run(
            equipment_id=key,
            equipment_code=eq.equipment_code,
            equipment_type=eq.equipment_type,
            equipment_name=eq.equipment_name,
            symptoms=symptoms,
            question=question,
        )
        return {
            "confidence": result.get("confidence"),
            "alternative_causes": result.get("alternative_causes", []),
            "symptoms": symptoms,
            "evidence_summary": result.get("evidence_summary", []),
            "recommendations": result.get("recommendations", {}),
            "spare_parts_needed": result.get("spare_parts_needed", []),
            "days_to_shutdown": result.get("days_to_shutdown"),
            "citations": result.get("citations", []),
            # Templated, human-readable report (relevance-filtered evidence) — the
            # same composed markdown surfaced by /agent/chat, for UIs that render
            # the stored health report directly.
            "report_markdown": result.get("report_markdown"),
        }

    async def _persist(
        self,
        key: str,
        eq: Equipment,
        prediction: HealthPrediction,
        report: dict[str, Any] | None,
        now: datetime,
    ) -> None:
        await self._health_repo.mark_stale(key)
        record = EquipmentHealthRecord(
            id=str(uuid.uuid4()),
            equipment_id=key,
            health_score=prediction.health_score,
            risk_level=prediction.risk_level,
            rul_days=prediction.rul_days,
            failure_probability=prediction.failure_probability,
            predicted_failure=(report or {}).get("diagnosis") or prediction.predicted_failure,
            preventive_actions_json=json.dumps(prediction.preventive_actions),
            expected_end_of_life_date=(
                prediction.expected_end_of_life_date.isoformat()
                if prediction.expected_end_of_life_date else None
            ),
            is_active=True,
            generated_at=(prediction.generated_at or now).isoformat(),
            agent_report_json=json.dumps(report) if report else None,
        )
        await self._health_repo.insert(record)

    # -- Stage 4: plant-level bottleneck ranking -------------------------
    def _bottleneck_ranking(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Rank suspect equipment by a composite operational-priority score."""
        ranked: list[dict[str, Any]] = []
        for r in results:
            if not r.get("suspect"):
                continue
            triage = r.get("triage", {})
            crit = _CRIT_RANK.get((r.get("criticality") or "").upper(), 0)
            risk = _RISK_RANK.get((r.get("risk_level") or "").upper(), 0)
            delay_sev = triage.get("max_delay_severity", 0)
            spares_penalty = min(triage.get("scarce_spares", 0), 3)
            lead = triage.get("min_spare_lead_days")
            lead_penalty = 1 if isinstance(lead, (int, float)) and lead > 14 else 0
            failed = 2 if (r.get("status") or "").upper() == "FAILED" else 0
            # Process criticality weighted highest, then condition risk, then
            # delay severity, then spares availability / lead time.
            score = 3 * crit + 2 * risk + delay_sev + spares_penalty + lead_penalty + failed
            ranked.append({
                "equipment_id": r.get("equipment_id"),
                "equipment_code": r.get("equipment_code"),
                "priority_score": score,
                "risk_level": r.get("risk_level"),
                "criticality": r.get("criticality"),
                "rul_days": r.get("rul_days"),
                "scarce_spares": triage.get("scarce_spares", 0),
                "min_spare_lead_days": lead,
            })
        ranked.sort(key=lambda x: x["priority_score"], reverse=True)
        for i, item in enumerate(ranked, start=1):
            item["rank"] = i
        return ranked


def build_agentic_health_service(db) -> AgenticHealthService:
    """Construct the agentic health service from the shared database."""
    return AgenticHealthService(db)
