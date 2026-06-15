"""Repository for the ``anomaly_alert`` table.

Columns: ``alert_id, equipment_id, equipment_name, category, timestamp,
sensor_name, observed_value, baseline_value, deviation_pct, alert_level,
detection_method, probable_cause, recommended_action, acknowledged,
acknowledged_by, resolution_status``. ``timestamp`` is stored as
``DD-MM-YYYY HH:MM`` text, so windowing is parsed in Python.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from database.connection import Database
from repositories.time_filters import parse_dt

_COLUMNS = (
    "alert_id, equipment_id, equipment_name, category, timestamp, sensor_name, "
    "observed_value, baseline_value, deviation_pct, alert_level, detection_method, "
    "probable_cause, recommended_action, acknowledged, acknowledged_by, resolution_status"
)


class AnomalyAlertRepository:
    """Read access to anomaly alerts with time/sensor/deviation filtering."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_for_equipment(
        self,
        equipment_id: str,
        *,
        since: datetime | None = None,
        before: datetime | None = None,
        sensor_name: str | None = None,
        min_deviation_pct: float | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return the latest ``limit`` alerts matching the filters, newest first.

        ``deviation_pct`` is matched as strictly greater than ``min_deviation_pct``
        and ``before`` as strictly earlier than the parsed timestamp, mirroring the
        agent ``get_anomaly_alert`` tool contract.
        """
        query = f"SELECT {_COLUMNS} FROM anomaly_alert WHERE equipment_id = ?"
        params: list[object] = [equipment_id]
        if sensor_name is not None:
            query += " AND sensor_name = ?"
            params.append(sensor_name)
        if min_deviation_pct is not None:
            query += " AND deviation_pct > ?"
            params.append(min_deviation_pct)
        rows = [dict(r) for r in await self._db.fetch_all(query, params)]

        out: list[tuple[datetime, dict[str, Any]]] = []
        for row in rows:
            ts = parse_dt(row.get("timestamp"))
            if ts is None:
                continue
            if since is not None and ts < since:
                continue
            if before is not None and ts >= before:
                continue
            out.append((ts, row))
        out.sort(key=lambda pair: pair[0], reverse=True)
        return [row for _, row in out[:limit]]
