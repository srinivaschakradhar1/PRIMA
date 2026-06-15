"""API routes for sensor reading ingestion."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_sensor_reading_service
from schemas.sensor_reading import SensorReadingBatchRequest, SensorReadingBatchResponse
from services.sensor_reading_service import SensorReadingService

router = APIRouter(tags=["Sensor Readings"])


@router.post("/sensor-readings/batch", response_model=SensorReadingBatchResponse)
async def ingest_sensor_readings_batch(
    batch: SensorReadingBatchRequest,
    service: SensorReadingService = Depends(get_sensor_reading_service),
) -> SensorReadingBatchResponse:
    return await service.ingest_batch(batch)
