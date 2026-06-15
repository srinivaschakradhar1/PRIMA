"""Repository for the ``spare_parts_inventory`` table.

Columns: ``part_id, equipment_id, equipment_name, category, part_name,
unit_of_measure, min_stock_level, max_stock_level, current_stock,
reorder_point, unit_cost_inr, preferred_vendor, alternate_vendor,
procurement_lead_time_days, criticality, stock_status,
last_procurement_date``. ``stock_status`` is one of ``Adequate`` /
``Reorder Required`` / ``Out of Stock``.

There is no spare-parts vector index, so spare-parts lookup is SQL-only.
"""

from __future__ import annotations

from typing import Any

from database.connection import Database

_COLUMNS = (
    "part_id, equipment_id, equipment_name, category, part_name, unit_of_measure, "
    "min_stock_level, max_stock_level, current_stock, reorder_point, unit_cost_inr, "
    "preferred_vendor, alternate_vendor, procurement_lead_time_days, criticality, "
    "stock_status, last_procurement_date"
)


class SparePartRepository:
    """Read access to the spare-parts inventory."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_for_equipment(
        self,
        equipment_id: str,
        *,
        part_query: str | None = None,
        stock_status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return spare parts for an equipment, optionally filtered.

        ``part_query`` matches ``part_name`` case-insensitively (substring); rows
        are ordered so the most procurement-sensitive parts surface first
        (out-of-stock / reorder before adequate, then by shortest lead time).
        """
        query = f"SELECT {_COLUMNS} FROM spare_parts_inventory WHERE equipment_id = ?"
        params: list[object] = [equipment_id]
        if part_query:
            query += " AND LOWER(part_name) LIKE ?"
            params.append(f"%{part_query.lower()}%")
        if stock_status is not None:
            query += " AND stock_status = ?"
            params.append(stock_status)
        # Surface scarce parts first: Out of Stock (0) -> Reorder Required (1) ->
        # everything else (2), then by shortest procurement lead time.
        query += (
            " ORDER BY CASE stock_status "
            "WHEN 'Out of Stock' THEN 0 WHEN 'Reorder Required' THEN 1 ELSE 2 END, "
            "procurement_lead_time_days ASC LIMIT ?"
        )
        params.append(limit)
        rows = await self._db.fetch_all(query, params)
        return [dict(row) for row in rows]
