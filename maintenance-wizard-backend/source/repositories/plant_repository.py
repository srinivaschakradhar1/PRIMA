"""Repository for the ``plant`` table."""

from __future__ import annotations

from database.connection import Database
from models.domain import Plant


class PlantRepository:
    """Data access layer for plant records."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_all(self) -> list[Plant]:
        rows = await self._db.fetch_all(
            "SELECT id, name, location, description, created_at, updated_at "
            "FROM plant ORDER BY id"
        )
        return [Plant.from_row(row) for row in rows]

    async def get_by_id(self, plant_id: str) -> Plant | None:
        row = await self._db.fetch_one(
            "SELECT id, name, location, description, created_at, updated_at "
            "FROM plant WHERE id = ?",
            (plant_id,),
        )
        return Plant.from_row(row) if row else None
