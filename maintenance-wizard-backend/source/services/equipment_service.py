"""Service layer for equipment-related business logic."""

from __future__ import annotations

import json

from models.domain import Equipment, EquipmentHealthRecord
from models.enums import RiskLevel
from repositories.equipment_repository import EquipmentRepository
from repositories.health_repository import HealthRepository
from schemas.equipment import (
    EquipmentDetailResponse,
    EquipmentHealthResponse,
    EquipmentListItemResponse,
    EquipmentStatusItemResponse,
    EquipmentStatusSummaryResponse,
    PreventiveAction,
    PreventiveActionsResponse,
)


class EquipmentService:
    """Business logic for equipment operations."""

    def __init__(
        self,
        equipment_repository: EquipmentRepository,
        health_repository: HealthRepository,
    ) -> None:
        self._equipment_repository = equipment_repository
        self._health_repository = health_repository

    @staticmethod
    def _to_risk_level(risk_level: str | None) -> RiskLevel | None:
        if risk_level is None:
            return None
        try:
            return RiskLevel(risk_level)
        except ValueError:
            return None

    async def list_equipment(
        self,
        plant_id: str | None = None,
        equipment_type: str | None = None,
        status: str | None = None,
        criticality: str | None = None,
    ) -> list[EquipmentListItemResponse]:
        equipment_list = await self._equipment_repository.list_all(
            plant_id=plant_id,
            equipment_type=equipment_type,
            status=status,
            criticality=criticality,
        )
        health_map = await self._health_repository.get_latest_active_for_all()

        results: list[EquipmentListItemResponse] = []
        for equipment in equipment_list:
            health_record = health_map.get(equipment.equipment_code)
            results.append(
                EquipmentListItemResponse(
                    id=equipment.id,
                    equipment_code=equipment.equipment_code,
                    equipment_name=equipment.equipment_name,
                    status=equipment.status,
                    health_score=health_record.health_score if health_record else None,
                    risk_of_failure=self._to_risk_level(
                        health_record.risk_level if health_record else None
                    ),
                )
            )
        return results

    async def get_equipment(self, equipment_id: str) -> EquipmentDetailResponse | None:
        equipment = await self._equipment_repository.get_by_id(equipment_id)
        if equipment is None:
            return None

        health_record = await self._health_repository.get_latest_active(equipment_id)

        return EquipmentDetailResponse(
            plant_id=equipment.plant_id,
            equipment_code=equipment.equipment_code,
            equipment_name=equipment.equipment_name,
            equipment_type=equipment.equipment_type,
            manufacturer=equipment.manufacturer,
            model_number=equipment.model_number,
            criticality=equipment.criticality,
            expected_life_days=equipment.expected_life_days,
            expected_end_of_life_date=(
                health_record.expected_end_of_life_date if health_record else None
            ),
            location_in_plant=equipment.location_in_plant,
            health=equipment.status,
            health_score=health_record.health_score if health_record else None,
            risk_of_failure=self._to_risk_level(
                health_record.risk_level if health_record else None
            ),
        )

    async def get_equipment_status(self) -> list[EquipmentStatusItemResponse]:
        equipment_list = await self._equipment_repository.list_all()
        health_map = await self._health_repository.get_latest_active_for_all()

        results: list[EquipmentStatusItemResponse] = []
        for equipment in equipment_list:
            health_record = health_map.get(equipment.equipment_code)
            results.append(
                EquipmentStatusItemResponse(
                    equipment_id=equipment.id,
                    equipment_name=equipment.equipment_name,
                    status=equipment.status,
                    health_score=health_record.health_score if health_record else None,
                    risk_of_failure=self._to_risk_level(
                        health_record.risk_level if health_record else None
                    ),
                )
            )
        return results

    async def get_status_summary(self) -> EquipmentStatusSummaryResponse:
        counts = await self._equipment_repository.get_status_summary()
        return EquipmentStatusSummaryResponse(
            UP=counts.get("UP", 0),
            FAILED=counts.get("FAILED", 0),
            SCHEDULED_DOWN=counts.get("SCHEDULED_DOWN", 0),
            MAINTENANCE=counts.get("MAINTENANCE", 0),
        )

    async def exists(self, equipment_id: str) -> bool:
        return await self._equipment_repository.exists(equipment_id)

    async def get_equipment_health(
        self, equipment_id: str
    ) -> EquipmentHealthResponse | None:
        if not await self._equipment_repository.exists(equipment_id):
            return None

        health_record = await self._health_repository.get_latest_active(equipment_id)
        if health_record is None:
            return EquipmentHealthResponse(
                equipment_id=equipment_id,
                health_score=None,
                risk=None,
                rul_days=None,
            )

        return EquipmentHealthResponse(
            equipment_id=equipment_id,
            health_score=health_record.health_score,
            risk=self._to_risk_level(health_record.risk_level),
            rul_days=health_record.rul_days,
        )

    async def get_preventive_actions(
        self, equipment_id: str
    ) -> PreventiveActionsResponse | None:
        equipment = await self._equipment_repository.get_by_id(equipment_id)
        if equipment is None:
            return None

        health_record = await self._health_repository.get_latest_active(equipment_id)

        actions: list[PreventiveAction] = []
        if health_record and health_record.preventive_actions_json:
            try:
                raw_actions = json.loads(health_record.preventive_actions_json)
            except (json.JSONDecodeError, TypeError):
                raw_actions = []

            for item in raw_actions:
                if isinstance(item, dict):
                    actions.append(
                        PreventiveAction(
                            priority=item.get("priority", 0),
                            action=item.get("action", ""),
                        )
                    )

        return PreventiveActionsResponse(
            equipment=equipment.equipment_name,
            actions=actions,
        )
