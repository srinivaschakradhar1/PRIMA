"""Pydantic schemas for the Plant resource."""

from __future__ import annotations

from schemas.common import CamelModel


class PlantResponse(CamelModel):
    """Response schema for a plant (used for both list and detail views)."""

    id: str
    name: str
    location: str
    description: str | None = None
