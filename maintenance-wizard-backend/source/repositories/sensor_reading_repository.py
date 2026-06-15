"""Repository for the ``sensor_reading`` table (daily-aggregated schema).

Columns: ``equipment_id, equipment_name, category, date, sensor_name,
avg_value, min_value, max_value, std_dev, status_flag`` where ``status_flag``
is one of ``Normal`` / ``Warning`` / ``Critical``. There is one row per sensor
per day. The legacy raw-reading schema (``value``/``reading_timestamp``/
``sensor_code``) no longer exists, so this repository returns plain dicts rather
than the old ``SensorReading`` domain model.

The ``date`` column is ISO ``YYYY-MM-DD`` (lexically sortable), so date-range
windowing is done in SQL here.
"""

from __future__ import annotations

from typing import Any

from database.connection import Database
from repositories.time_filters import cutoff

_COLUMNS = (
    "equipment_id, equipment_name, category, date, sensor_name, "
    "avg_value, min_value, max_value, std_dev, status_flag"
)


class SensorReadingRepository:
    """Read access to daily-aggregated sensor readings."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_by_equipment(
        self,
        equipment_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return readings for an equipment within an optional ``YYYY-MM-DD`` range.

        Rows are ordered by ``date`` ascending (and ``sensor_name``) so callers
        can compute per-channel trends directly.
        """
        query = f"SELECT {_COLUMNS} FROM sensor_reading WHERE equipment_id = ?"
        params: list[object] = [equipment_id]
        if start_date is not None:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date is not None:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date ASC, sensor_name ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        rows = await self._db.fetch_all(query, params)
        return [dict(row) for row in rows]

    async def recent_window(
        self, equipment_id: str, days: float = 5.0
    ) -> list[dict[str, Any]]:
        """Return readings from the last ``days`` days (anchored on now)."""
        start = cutoff(days).strftime("%Y-%m-%d")
        return await self.list_by_equipment(equipment_id, start_date=start)
