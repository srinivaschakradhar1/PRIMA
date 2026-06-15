"""Repository for the ``fault_error_message`` table.

Columns: ``msg_id, equipment_id, equipment_name, category, timestamp,
fault_code, message_text, message_type, source_system, acknowledged_by,
ack_time``. ``timestamp`` is ``DD-MM-YYYY HH:MM`` text → windowed in Python.
``message_type`` is one of ``Alarm`` / ``Fault`` / ``Trip`` / ``Warning``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from database.connection import Database
from repositories.time_filters import parse_dt

_COLUMNS = (
    "msg_id, equipment_id, equipment_name, category, timestamp, fault_code, "
    "message_text, message_type, source_system, acknowledged_by, ack_time"
)


class FaultMessageRepository:
    """Read access to SCADA/PLC fault & alarm messages."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_for_equipment(
        self,
        equipment_id: str,
        *,
        since: datetime | None = None,
        message_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return the latest ``limit`` fault messages, newest first."""
        query = f"SELECT {_COLUMNS} FROM fault_error_message WHERE equipment_id = ?"
        params: list[object] = [equipment_id]
        if message_type is not None:
            query += " AND message_type = ?"
            params.append(message_type)
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
