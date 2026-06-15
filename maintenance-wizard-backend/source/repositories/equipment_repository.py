"""Repository for the ``equipment`` table."""

from __future__ import annotations

from database.connection import Database
from models.domain import Equipment


class EquipmentRepository:
    """Data access layer for equipment records."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_all(
        self,
        plant_id: str | None = None,
        equipment_type: str | None = None,
        status: str | None = None,
        criticality: str | None = None,
    ) -> list[Equipment]:
        query = (
            "SELECT id, plant_id, equipment_code, equipment_name, equipment_type, "
            "manufacturer, model_number, installation_date, expected_life_days, "
            "criticality, location_in_plant, status, created_at, updated_at "
            "FROM equipment WHERE 1=1"
        )
        params: list[object] = []

        if plant_id is not None:
            query += " AND plant_id = ?"
            params.append(plant_id)
        if equipment_type is not None:
            query += " AND equipment_type = ?"
            params.append(equipment_type)
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        if criticality is not None:
            query += " AND criticality = ?"
            params.append(criticality)

        query += " ORDER BY id"

        rows = await self._db.fetch_all(query, params)
        return [Equipment.from_row(row) for row in rows]

    async def get_by_id(self, equipment_id: str) -> Equipment | None:
        row = await self._db.fetch_one(
            "SELECT id, plant_id, equipment_code, equipment_name, equipment_type, "
            "manufacturer, model_number, installation_date, expected_life_days, "
            "criticality, location_in_plant, status, created_at, updated_at "
            "FROM equipment WHERE id = ?",
            (equipment_id,),
        )
        return Equipment.from_row(row) if row else None

    async def get_by_code(self, equipment_code: str) -> Equipment | None:
        row = await self._db.fetch_one(
            "SELECT id, plant_id, equipment_code, equipment_name, equipment_type, "
            "manufacturer, model_number, installation_date, expected_life_days, "
            "criticality, location_in_plant, status, created_at, updated_at "
            "FROM equipment WHERE equipment_code = ?",
            (equipment_code,),
        )
        return Equipment.from_row(row) if row else None

    def get_by_code_sync(self, equipment_code: str) -> Equipment | None:
        """Synchronous lookup for use inside non-async record builders.

        Uses the blocking ``sqlite3`` cursor directly (no event loop / lock),
        so it must only be called from a synchronous code path.
        """
        cursor = self._db._execute(
            "SELECT id, plant_id, equipment_code, equipment_name, equipment_type, "
            "manufacturer, model_number, installation_date, expected_life_days, "
            "criticality, location_in_plant, status, created_at, updated_at "
            "FROM equipment WHERE equipment_code = ?",
            (equipment_code,),
        )
        row = cursor.fetchone()
        return Equipment.from_row(row) if row else None

    async def get_status_summary(self) -> dict[str, int]:
        rows = await self._db.fetch_all(
            "SELECT status, COUNT(*) AS cnt FROM equipment GROUP BY status"
        )
        return {row["status"]: row["cnt"] for row in rows}

    async def exists(self, equipment_id: str) -> bool:
        row = await self._db.fetch_one(
            "SELECT 1 FROM equipment WHERE id = ?", (equipment_id,)
        )
        return row is not None

    async def update_status(self, equipment_id: str, status: str) -> None:
        await self._db.execute_and_commit(
            "UPDATE equipment SET status = ? WHERE id = ?",
            (status, equipment_id),
        )
