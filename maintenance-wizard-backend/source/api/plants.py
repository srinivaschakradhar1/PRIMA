"""API routes for plant resources."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_plant_service
from api.exceptions import NotFoundError
from schemas.common import MessageResponse
from schemas.plant import PlantResponse
from services.plant_service import PlantService

router = APIRouter(tags=["Plants"])


@router.get("/plants", response_model=list[PlantResponse])
async def list_plants(
    service: PlantService = Depends(get_plant_service),
) -> list[PlantResponse]:
    return await service.list_plants()


@router.get(
    "/plants/{plant_id}",
    response_model=PlantResponse,
    responses={404: {"model": MessageResponse}},
)
async def get_plant(
    plant_id: str,
    service: PlantService = Depends(get_plant_service),
) -> PlantResponse:
    plant = await service.get_plant(plant_id)
    if plant is None:
        raise NotFoundError("Plant not found")
    return plant
