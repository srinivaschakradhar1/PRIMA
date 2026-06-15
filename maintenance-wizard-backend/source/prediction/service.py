"""Health-prediction orchestration and persistence.

Pulls each equipment's sensors + recent readings, runs the deterministic
:mod:`prediction.engine`, and writes a fresh ``equipment_health_record`` row
(marking the previous active row stale so history is preserved). Used by the
startup hook, the scheduled background job, and the manual refresh endpoint.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from models.domain import EquipmentHealthRecord
from prediction.engine import HealthPrediction, predict_health
from repositories.equipment_repository import EquipmentRepository
from repositories.health_repository import HealthRepository
from repositories.sensor_reading_repository import SensorReadingRepository
from repositories.time_filters import cutoff

logger = logging.getLogger(__name__)

# History window (days) fed to the engine for a stable health estimate.
_HEALTH_WINDOW_DAYS = 30.0


class HealthPredictionService:
    """Computes and persists equipment health predictions from sensor data."""

    def __init__(
        self,
        equipment_repository: EquipmentRepository,
        sensor_reading_repository: SensorReadingRepository,
        health_repository: HealthRepository,
    ) -> None:
        self._equipment_repo = equipment_repository
        self._reading_repo = sensor_reading_repository
        self._health_repo = health_repository

    async def refresh_all(self, now: datetime | None = None) -> dict[str, Any]:
        """Recompute and persist health for every equipment. Returns a summary."""
        now = now or datetime.now(timezone.utc)
        await self._health_repo.ensure_columns()
        equipment = await self._equipment_repo.list_all()
        results: list[dict[str, Any]] = []
        for eq in equipment:
            try:
                prediction = await self._predict_one(eq.id, now)
                if prediction is not None:
                    results.append(self._summary(prediction))
            except Exception:  # one bad equipment must not abort the batch
                logger.exception("Health prediction failed for equipment %s", eq.id)
        logger.info("Health prediction refresh complete for %d equipment.", len(results))
        return {"refreshed": len(results), "generated_at": now.isoformat(), "equipment": results}

    async def refresh_one(self, equipment_id: str, now: datetime | None = None) -> dict[str, Any] | None:
        """Recompute and persist health for a single equipment (key = code)."""
        now = now or datetime.now(timezone.utc)
        await self._health_repo.ensure_columns()
        if not await self._equipment_repo.exists(equipment_id):
            return None
        prediction = await self._predict_one(equipment_id, now)
        return self._summary(prediction) if prediction is not None else None

    # -- internals -------------------------------------------------------
    async def _predict_one(self, equipment_id: str, now: datetime) -> HealthPrediction | None:
        equipment = await self._equipment_repo.get_by_id(equipment_id)
        if equipment is None:
            return None

        # The time-series tables (sensor_reading, ...) key on the operational
        # *code* (e.g. RMHP-001), while the rest of the app keys on the internal
        # id (e.g. eq-001). Translate id -> code for the readings lookup.
        start = cutoff(_HEALTH_WINDOW_DAYS).strftime("%Y-%m-%d")
        readings = await self._reading_repo.list_by_equipment(
            equipment.equipment_code or equipment_id, start_date=start
        )

        prediction = predict_health(equipment, readings, now=now)
        # Persist under the internal id so the health/report endpoints (which
        # resolve via get_by_id) can read it back.
        prediction.equipment_id = equipment_id
        await self._persist(prediction)
        return prediction

    async def _persist(self, prediction: HealthPrediction) -> None:
        # Supersede the previous active record, then write the fresh one.
        await self._health_repo.mark_stale(prediction.equipment_id)
        record = EquipmentHealthRecord(
            id=str(uuid.uuid4()),
            equipment_id=prediction.equipment_id,
            health_score=prediction.health_score,
            risk_level=prediction.risk_level,
            rul_days=prediction.rul_days,
            failure_probability=prediction.failure_probability,
            predicted_failure=prediction.predicted_failure,
            preventive_actions_json=json.dumps(prediction.preventive_actions),
            expected_end_of_life_date=(
                prediction.expected_end_of_life_date.isoformat()
                if prediction.expected_end_of_life_date else None
            ),
            is_active=True,
            generated_at=(prediction.generated_at or datetime.now(timezone.utc)).isoformat(),
        )
        await self._health_repo.insert(record)

    @staticmethod
    def _summary(prediction: HealthPrediction) -> dict[str, Any]:
        return {
            "equipment_id": prediction.equipment_id,
            "health_score": prediction.health_score,
            "risk_level": prediction.risk_level,
            "rul_days": prediction.rul_days,
            "failure_probability": prediction.failure_probability,
            "predicted_failure": prediction.predicted_failure,
            "abnormal_symptoms": prediction.abnormal_symptoms,
            "preventive_actions": prediction.preventive_actions,
        }


def build_health_prediction_service(db) -> HealthPredictionService:
    """Construct the service from the shared database (used by jobs/startup/deps)."""
    return HealthPredictionService(
        equipment_repository=EquipmentRepository(db),
        sensor_reading_repository=SensorReadingRepository(db),
        health_repository=HealthRepository(db),
    )
