"""Repository for the ``equipment_delay_log`` table.

Columns: ``log_id, equipment_id, equipment_name, category, timestamp, shift,
delay_type, cause_description, duration_minutes, severity,
corrective_action_taken, reported_by, production_loss_tonnes``. ``timestamp``
is ``YYYY-MM-DD HH:MM:SS`` text. ``severity`` is one of
``Critical`` / ``High`` / ``Medium`` / ``Low``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from database.connection import Database
from repositories.time_filters import parse_dt

_COLUMNS = (
    "log_id, equipment_id, equipment_name, category, timestamp, shift, delay_type, "
    "cause_description, duration_minutes, severity, corrective_action_taken, "
    "reported_by, production_loss_tonnes"
)


class DelayLogRepository:
    """Read access to production delay / breakdown logs."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_for_equipment(
        self,
        equipment_id: str,
        *,
        since: datetime | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return the latest ``limit`` delay entries, newest first."""
        query = f"SELECT {_COLUMNS} FROM equipment_delay_log WHERE equipment_id = ?"
        params: list[object] = [equipment_id]
        if severity is not None:
            query += " AND severity = ?"
            params.append(severity)
        rows = [dict(r) for r in await self._db.fetch_all(query, params)]

        out: list[tuple[datetime, dict[str, Any]]] = []
        for row in rows:
            ts = parse_dt(row.get("timestamp"))
            if ts is None:
                continue
            if since is not None and ts < since:
                continue
            out.append((ts, row))
        out.sort(key=lambda pair: pair[0], reverse=True)
        return [row for _, row in out[:limit]]
