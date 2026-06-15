"""API routes for equipment resources."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query

from api.deps import (
    get_agentic_health_service,
    get_equipment_service,
    get_health_prediction_service,
)
from api.exceptions import NotFoundError
from database.connection import db
from models.enums import Criticality, EquipmentStatus
from prediction.agentic_service import AgenticHealthService
from repositories.health_repository import HealthRepository
from schemas.equipment import (
    EquipmentDetailResponse,
    EquipmentHealthResponse,
    EquipmentListItemResponse,
    EquipmentStatusItemResponse,
    EquipmentStatusSummaryResponse,
    HealthPredictionItem,
    HealthRefreshResponse,
    PreventiveActionsResponse,
)
from prediction.service import HealthPredictionService
from services.equipment_service import EquipmentService

router = APIRouter(tags=["Equipment"])


@router.post("/equipment/health/refresh", response_model=HealthRefreshResponse)
async def refresh_all_health_predictions(
    service: HealthPredictionService = Depends(get_health_prediction_service),
) -> HealthRefreshResponse:
    """Recompute health/RUL/failure predictions for every equipment from sensor
    data and persist them to ``equipment_health_record``."""
    summary = await service.refresh_all()
    return HealthRefreshResponse(**summary)


@router.post("/equipment/health/refresh-agentic")
async def refresh_all_health_agentic(
    service: AgenticHealthService = Depends(get_agentic_health_service),
) -> dict:
    """Run the full agentic pipeline for every equipment: deterministic triage,
    LLM deep-analysis of suspect equipment, persistence and plant-level
    bottleneck ranking. Returns the run summary (heavier than the deterministic
    ``/equipment/health/refresh``)."""
    return await service.refresh_all()


@router.get("/equipment/{equipment_id}/report")
async def get_equipment_report(equipment_id: str) -> dict:
    """Return the latest persisted health record plus the agent's structured
    maintenance report (diagnosis, root cause, corrective actions, spare parts,
    days-to-shutdown and citations) for a single equipment."""
    record = await HealthRepository(db).get_latest_active(equipment_id)
    if record is None:
        raise NotFoundError("No health record found for equipment")
    report = None
    if record.agent_report_json:
        try:
            report = json.loads(record.agent_report_json)
        except (ValueError, TypeError):
            report = None
    return {
        "equipment_id": record.equipment_id,
        "health_score": record.health_score,
        "risk_level": record.risk_level,
        "rul_days": record.rul_days,
        "failure_probability": record.failure_probability,
        "predicted_failure": record.predicted_failure,
        "generated_at": record.generated_at,
        "agent_report": report,
    }


@router.post(
    "/equipment/{equipment_id}/health/refresh", response_model=HealthPredictionItem
)
async def refresh_equipment_health_prediction(
    equipment_id: str,
    service: HealthPredictionService = Depends(get_health_prediction_service),
) -> HealthPredictionItem:
    """Recompute and persist the health prediction for a single equipment."""
    result = await service.refresh_one(equipment_id)
    if result is None:
        raise NotFoundError("Equipment not found")
    return HealthPredictionItem(**result)


@router.get("/equipment", response_model=list[EquipmentListItemResponse])
async def list_equipment(
    plantId: str | None = Query(default=None),
    equipmentType: str | None = Query(default=None),
    status: EquipmentStatus | None = Query(default=None),
    criticality: Criticality | None = Query(default=None),
    service: EquipmentService = Depends(get_equipment_service),
) -> list[EquipmentListItemResponse]:
    return await service.list_equipment(
        plant_id=plantId,
        equipment_type=equipmentType,
        status=status.value if status else None,
        criticality=criticality.value if criticality else None,
    )


@router.get("/equipment/status", response_model=list[EquipmentStatusItemResponse])
async def get_equipment_status(
    service: EquipmentService = Depends(get_equipment_service),
) -> list[EquipmentStatusItemResponse]:
    return await service.get_equipment_status()


@router.get("/equipment/status-summary", response_model=EquipmentStatusSummaryResponse)
async def get_equipment_status_summary(
    service: EquipmentService = Depends(get_equipment_service),
) -> EquipmentStatusSummaryResponse:
    return await service.get_status_summary()


@router.get("/equipment/{equipment_id}", response_model=EquipmentDetailResponse)
async def get_equipment(
    equipment_id: str,
    service: EquipmentService = Depends(get_equipment_service),
) -> EquipmentDetailResponse:
    equipment = await service.get_equipment(equipment_id)
    if equipment is None:
        raise NotFoundError("Equipment not found")
    return equipment


@router.get("/equipment/{equipment_id}/health", response_model=EquipmentHealthResponse)
async def get_equipment_health(
    equipment_id: str,
    service: EquipmentService = Depends(get_equipment_service),
) -> EquipmentHealthResponse:
    health = await service.get_equipment_health(equipment_id)
    if health is None:
        raise NotFoundError("Equipment not found")
    return health


@router.get(
    "/equipment/{equipment_id}/preventive-actions",
    response_model=PreventiveActionsResponse,
)
async def get_preventive_actions(
    equipment_id: str,
    service: EquipmentService = Depends(get_equipment_service),
) -> PreventiveActionsResponse:
    actions = await service.get_preventive_actions(equipment_id)
    if actions is None:
        raise NotFoundError("Equipment not found")
    return actions
