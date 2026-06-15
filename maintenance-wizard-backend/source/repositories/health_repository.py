"""Repository for the ``equipment_health_record`` table."""

from __future__ import annotations

from database.connection import Database
from models.domain import EquipmentHealthRecord


class HealthRepository:
    """Data access layer for equipment health record records."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def ensure_columns(self) -> None:
        """Add the ``agent_report_json`` column if the table predates it.

        ``equipment_health_record`` is recreated from its (header-only) seed CSV on
        every startup, so the column is added idempotently here rather than relying
        on a static DDL that the loader would overwrite.
        """
        try:
            await self._db.execute_and_commit(
                "ALTER TABLE equipment_health_record ADD COLUMN agent_report_json TEXT"
            )
        except Exception:
            pass  # already exists

    async def get_latest_active(self, equipment_id: str) -> EquipmentHealthRecord | None:
        row = await self._db.fetch_one(
            "SELECT * FROM equipment_health_record "
            "WHERE equipment_id = ? AND is_active = 1 "
            "ORDER BY generated_at DESC LIMIT 1",
            (equipment_id,),
        )
        return EquipmentHealthRecord.from_row(row) if row else None

    async def get_latest_active_for_all(self) -> dict[str, EquipmentHealthRecord]:
        """Return a mapping of equipment_id -> latest active health record."""
        rows = await self._db.fetch_all(
            "SELECT * FROM equipment_health_record WHERE is_active = 1"
        )
        result: dict[str, EquipmentHealthRecord] = {}
        for row in rows:
            record = EquipmentHealthRecord.from_row(row)
            if record.equipment_id:
                result[record.equipment_id] = record
        return result

    async def mark_stale(self, equipment_id: str) -> None:
        await self._db.execute_and_commit(
            "UPDATE equipment_health_record SET is_active = 0 "
            "WHERE equipment_id = ? AND is_active = 1",
            (equipment_id,),
        )

    async def insert(self, record: EquipmentHealthRecord) -> None:
        await self._db.execute_and_commit(
            "INSERT INTO equipment_health_record "
            "(id, equipment_id, health_score, risk_level, rul_days, failure_probability, "
            "predicted_failure, preventive_actions_json, expected_end_of_life_date, "
            "is_active, generated_at, agent_report_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.equipment_id,
                record.health_score,
                record.risk_level,
                record.rul_days,
                record.failure_probability,
                record.predicted_failure,
                record.preventive_actions_json,
                record.expected_end_of_life_date,
                int(record.is_active),
                record.generated_at,
                record.agent_report_json,
            ),
        )
