"""Pydantic schemas for the Equipment resource."""

from __future__ import annotations

from datetime import date

from pydantic import Field

from models.enums import Criticality, EquipmentStatus, RiskLevel
from schemas.common import CamelModel


class EquipmentListItemResponse(CamelModel):
    """Response schema for an item in the equipment list (GET /equipment)."""

    id: str
    equipment_code: str | None = None
    equipment_name: str | None = None
    status: str | None = None
    health_score: float | None = None
    risk_of_failure: RiskLevel | None = None


class EquipmentDetailResponse(CamelModel):
    """Response schema for equipment detail (GET /equipment/{equipmentId})."""

    plant_id: str | None = None
    equipment_code: str | None = None
    equipment_name: str | None = None
    equipment_type: str | None = None
    manufacturer: str | None = None
    model_number: str | None = None
    criticality: Criticality | None = None
    expected_life_days: int | None = None
    expected_end_of_life_date: date | None = None
    location_in_plant: str | None = None
    health: str | None = None
    health_score: int | None = None
    risk_of_failure: RiskLevel | None = None


class EquipmentStatusItemResponse(CamelModel):
    """Response schema for an item in GET /equipment/status."""

    equipment_id: str
    equipment_name: str | None = None
    status: str | None = None
    health_score: int | None = None
    risk_of_failure: RiskLevel | None = None


class EquipmentStatusSummaryResponse(CamelModel):
    """Response schema for GET /equipment/status-summary."""

    UP: int = 0
    FAILED: int = 0
    SCHEDULED_DOWN: int = 0
    MAINTENANCE: int = 0


class EquipmentHealthResponse(CamelModel):
    """Response schema for GET /equipment/{id}/health."""

    equipment_id: str
    health_score: int | None = None
    risk: RiskLevel | None = None
    rul_days: int | None = None


class PreventiveAction(CamelModel):
    """A single preventive action item."""

    priority: int
    action: str


class PreventiveActionsResponse(CamelModel):
    """Response schema for GET /equipment/{id}/preventive-actions."""

    equipment: str | None = None
    actions: list[PreventiveAction] = Field(default_factory=list)


class HealthPredictionItem(CamelModel):
    """A single equipment's freshly computed health prediction."""

    equipment_id: str
    health_score: int | None = None
    risk_level: RiskLevel | None = None
    rul_days: int | None = None
    failure_probability: float | None = None
    predicted_failure: str | None = None
    abnormal_symptoms: list[str] = Field(default_factory=list)
    preventive_actions: list[PreventiveAction] = Field(default_factory=list)


class HealthRefreshResponse(CamelModel):
    """Response for the health prediction refresh endpoints."""

    refreshed: int
    generated_at: str | None = None
    equipment: list[HealthPredictionItem] = Field(default_factory=list)
