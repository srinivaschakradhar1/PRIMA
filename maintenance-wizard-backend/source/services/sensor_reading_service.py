"""Service layer for sensor reading ingestion.

The ``sensor_reading`` table is now daily-aggregated (one row per sensor per day
with ``avg/min/max/std`` + a ``status_flag``) and is populated from the seed
data at startup. Raw per-reading streaming ingestion no longer maps onto this
schema, so this service validates the incoming batch against known equipment and
acknowledges it without persisting individual raw samples. It is kept so the
``/sensor-readings/batch`` endpoint and its contract remain available.
"""

from __future__ import annotations

import logging

from repositories.equipment_repository import EquipmentRepository
from schemas.sensor_reading import SensorReadingBatchRequest, SensorReadingBatchResponse

logger = logging.getLogger(__name__)


class SensorReadingService:
    """Validates batches of sensor readings against the equipment registry."""

    def __init__(self, equipment_repository: EquipmentRepository) -> None:
        self._equipment_repository = equipment_repository

    async def ingest_batch(
        self, batch: SensorReadingBatchRequest
    ) -> SensorReadingBatchResponse:
        accepted = 0
        rejected = 0
        for item in batch.readings:
            if await self._equipment_repository.exists(item.equipment_id):
                accepted += 1
            else:
                logger.warning(
                    "Rejected sensor reading: unknown equipment_id=%s", item.equipment_id
                )
                rejected += 1
        if accepted:
            logger.info(
                "Acknowledged %d sensor readings; the aggregated sensor_reading "
                "schema does not persist raw per-reading samples.",
                accepted,
            )
        return SensorReadingBatchResponse(accepted=accepted, rejected=rejected)
