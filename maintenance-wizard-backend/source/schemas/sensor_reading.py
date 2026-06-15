"""Pydantic schemas for sensor readings."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from schemas.common import CamelModel


class SensorReadingItem(CamelModel):
    """A single sensor reading submitted in a batch."""

    equipment_id: str
    sensor_code: str
    value: float
    timestamp: datetime


class SensorReadingBatchRequest(CamelModel):
    """Request schema for POST /sensor-readings/batch."""

    readings: list[SensorReadingItem] = Field(default_factory=list)


class SensorReadingBatchResponse(CamelModel):
    """Response schema for POST /sensor-readings/batch."""

    accepted: int
    rejected: int
