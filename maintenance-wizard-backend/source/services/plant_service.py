"""Service layer for plant-related business logic."""

from __future__ import annotations

from repositories.plant_repository import PlantRepository
from schemas.plant import PlantResponse


class PlantService:
    """Business logic for plant operations."""

    def __init__(self, plant_repository: PlantRepository) -> None:
        self._plant_repository = plant_repository

    async def list_plants(self) -> list[PlantResponse]:
        plants = await self._plant_repository.list_all()
        return [
            PlantResponse(
                id=plant.id,
                name=plant.name,
                location=plant.location,
                description=plant.description,
            )
            for plant in plants
        ]

    async def get_plant(self, plant_id: str) -> PlantResponse | None:
        plant = await self._plant_repository.get_by_id(plant_id)
        if plant is None:
            return None
        return PlantResponse(
            id=plant.id,
            name=plant.name,
            location=plant.location,
            description=plant.description,
        )
