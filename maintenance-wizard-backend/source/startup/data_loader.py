"""Startup data loading.

Reads the top-level CSV files in ``data/`` and loads each one into a SQLite
table named after the file (``plant.csv`` -> ``plant``). The table schema is
derived from the file itself, following the documented startup sequence:

    Load CSV Files -> Populate SQLite Tables -> Initialize FAISS -> Start FastAPI

Design notes:

* The table for each CSV is dropped and recreated on every startup so its
  schema always matches the current file. Column types are inferred from the
  header plus the first couple of data rows only (we never scan the whole file
  just to build the DDL).
* A file containing only a header row (no data) results in the table being
  created but left empty.
* For the time-series files listed in ``TIMESTAMP_SHIFT_TABLES`` the
  ``timestamp`` / ``date`` column is shifted forward so that the newest record
  lands at "now". This keeps the data fresh on every boot, which the proactive
  failure-detection agent relies on.

Tables that have no backing CSV (``sensor``, the ``knowledge_*`` /
``agent_*`` tables, etc.) are created separately via ``ALL_TABLES_SCRIPT``.
"""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from database.connection import Database
from database.schema import ALL_TABLES_SCRIPT

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Internal table used as a one-time-initialization marker. Once the seed data
# has been loaded successfully we record a row here; subsequent startups see it
# and skip the (destructive) reload. The flag lives inside the SQLite database
# itself so it travels with the data file and needs no external state.
_META_TABLE = "_app_metadata"
_INIT_KEY = "db_initialized"

# Set FORCE_DB_INIT=1 (truthy) in the environment to force a full reload even if
# the marker is present, e.g. after shipping new seed CSVs to the server.
_FORCE_INIT_ENV = "FORCE_DB_INIT"

# Tables whose ``timestamp`` / ``date`` column is shifted so the most recent
# record is moved to the current time (the same delta is applied to every row).
TIMESTAMP_SHIFT_TABLES = {
    "anomaly_alert",
    "fault_error_message",
    "equipment_delay_log",
    "sensor_reading",
}

# Names (lower-cased) of the column treated as the record time, in priority
# order, for tables in ``TIMESTAMP_SHIFT_TABLES``.
_TIME_COLUMN_NAMES = ("timestamp", "date")

# Datetime formats seen across the seed CSVs, tried in order. The matched
# format is reused when writing the shifted value back so the original textual
# representation is preserved.
_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d-%m-%Y",
)


def _is_int(value: str) -> bool:
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


def _is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _infer_type(samples: list[str]) -> str:
    """Infer a SQLite column type from a handful of sample values."""
    values = [s for s in samples if s is not None and str(s).strip() != ""]
    if not values:
        return "TEXT"
    if all(_is_int(v) for v in values):
        return "INTEGER"
    if all(_is_float(v) for v in values):
        return "REAL"
    return "TEXT"


def _parse_datetime(value: str) -> tuple[datetime, str] | None:
    """Parse ``value`` against the known formats, returning ``(dt, fmt)``."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt), fmt
        except ValueError:
            continue
    return None


def _is_blank_row(values: list[str]) -> bool:
    return all(v is None or str(v).strip() == "" for v in values)


def _read_header(reader: "csv._reader") -> tuple[list[int], list[str]]:
    """Read the header row and return (valid column indices, column names).

    Trailing/empty header cells (produced by spreadsheets padding rows with
    extra commas) are ignored.
    """
    try:
        header = next(reader)
    except StopIteration:
        return [], []
    valid_idx = [i for i, name in enumerate(header) if name and name.strip()]
    columns = [header[i].strip() for i in valid_idx]
    return valid_idx, columns


def _select(raw: list[str], valid_idx: list[int]) -> list[str]:
    return [raw[i] if i < len(raw) else "" for i in valid_idx]


def _sniff_schema(path: Path) -> tuple[list[str], list[str]]:
    """Infer (columns, column types) from the header and first two data rows."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        valid_idx, columns = _read_header(reader)
        if not columns:
            return [], []

        samples: list[list[str]] = []
        for raw in reader:
            values = _select(raw, valid_idx)
            if _is_blank_row(values):
                continue
            samples.append(values)
            if len(samples) >= 2:
                break

    types = [
        _infer_type([row[col_idx] for row in samples])
        for col_idx in range(len(columns))
    ]
    return columns, types


def _read_data_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    """Read every non-blank data row from ``path``."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        valid_idx, columns = _read_header(reader)
        if not columns:
            return [], []

        rows: list[list[str]] = []
        for raw in reader:
            values = _select(raw, valid_idx)
            if _is_blank_row(values):
                continue
            rows.append(values)
    return columns, rows


def _shift_timestamps(table: str, columns: list[str], rows: list[list[str]]) -> None:
    """Shift the time column so the latest record lands at the current time.

    The maximum value across all rows is found, the delta needed to bring it to
    ``datetime.now()`` is computed, and that same delta is added to every row.
    Rows are mutated in place; the original textual format is preserved.
    """
    lower = [c.lower() for c in columns]
    target = next(
        (lower.index(name) for name in _TIME_COLUMN_NAMES if name in lower),
        None,
    )
    if target is None:
        logger.warning(
            "Table '%s' is flagged for timestamp shifting but has no "
            "'timestamp'/'date' column; leaving values unchanged.", table
        )
        return

    parsed: list[tuple[datetime, str] | None] = []
    max_dt: datetime | None = None
    for row in rows:
        result = _parse_datetime(row[target])
        parsed.append(result)
        if result is not None and (max_dt is None or result[0] > max_dt):
            max_dt = result[0]

    if max_dt is None:
        logger.warning(
            "Table '%s': no parseable values in column '%s'; "
            "leaving values unchanged.", table, columns[target]
        )
        return

    delta: timedelta = datetime.now() - max_dt
    for row, result in zip(rows, parsed):
        if result is None:
            continue
        dt, fmt = result
        row[target] = (dt + delta).strftime(fmt)

    logger.info(
        "Table '%s': shifted column '%s' by %s (max %s -> now).",
        table, columns[target], delta, max_dt.isoformat(),
    )


def _build_create_sql(table: str, columns: list[str], types: list[str]) -> str:
    column_defs = ",\n    ".join(
        f'"{col}" {col_type}' for col, col_type in zip(columns, types)
    )
    return f'CREATE TABLE "{table}" (\n    {column_defs}\n);'


async def _load_csv(db: Database, path: Path) -> None:
    table = path.stem

    columns, types = _sniff_schema(path)
    if not columns:
        logger.warning("Skipping '%s': no header row found.", path.name)
        return

    # Recreate the table so its schema always matches the current file.
    await db.execute_and_commit(f'DROP TABLE IF EXISTS "{table}"')
    await db.execute_and_commit(_build_create_sql(table, columns, types))

    _, rows = _read_data_rows(path)
    if not rows:
        logger.info("Created empty table '%s' (header-only file %s).", table, path.name)
        return

    if table in TIMESTAMP_SHIFT_TABLES:
        _shift_timestamps(table, columns, rows)

    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(f'"{col}"' for col in columns)
    query = f'INSERT INTO "{table}" ({column_list}) VALUES ({placeholders})'

    # Empty cells become NULL so numeric columns are not polluted with "".
    params = [
        tuple(None if (v is None or str(v) == "") else v for v in row)
        for row in rows
    ]
    await db.executemany_and_commit(query, params)

    logger.info("Loaded %d rows into table '%s' from %s", len(params), table, path.name)


def _force_init_requested() -> bool:
    """True if the FORCE_DB_INIT env var is set to a truthy value."""
    return os.environ.get(_FORCE_INIT_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


async def _already_initialized(db: Database) -> bool:
    """Return True if a previous run already loaded the seed data."""
    row = await db.fetch_one(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (_META_TABLE,),
    )
    if row is None:
        return False
    flag = await db.fetch_one(
        f'SELECT value FROM "{_META_TABLE}" WHERE key=?', (_INIT_KEY,)
    )
    return flag is not None


async def _mark_initialized(db: Database) -> None:
    """Record that the seed data has been loaded successfully."""
    await db.execute_and_commit(
        f'CREATE TABLE IF NOT EXISTS "{_META_TABLE}" '
        f"(key TEXT PRIMARY KEY, value TEXT)"
    )
    await db.execute_and_commit(
        f'INSERT OR REPLACE INTO "{_META_TABLE}" (key, value) VALUES (?, ?)',
        (_INIT_KEY, datetime.now().isoformat()),
    )


async def initialize_database(db: Database) -> None:
    """Create static tables and populate one table per CSV file, but only once.

    The seed load is destructive (it drops and recreates every CSV-backed table
    and shifts timestamps forward to "now"). On a long-running server we only
    want this on the very first boot, so a marker row in ``_app_metadata`` guards
    against re-running it on subsequent restarts. Set ``FORCE_DB_INIT=1`` to
    override and force a full reload (e.g. after updating the seed CSVs).
    """
    if await _already_initialized(db):
        if not _force_init_requested():
            logger.info(
                "Database already initialized (marker present); skipping seed "
                "data load. Set %s=1 to force a reload.", _FORCE_INIT_ENV
            )
            return
        logger.info(
            "%s is set; forcing a full reload of the seed data.", _FORCE_INIT_ENV
        )

    logger.info("Initializing database from seed CSV files...")
    await db.executescript(ALL_TABLES_SCRIPT)

    for path in sorted(DATA_DIR.glob("*.csv")):
        await _load_csv(db, path)

    await _mark_initialized(db)
    logger.info("Database initialization complete.")
