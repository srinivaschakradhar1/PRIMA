"""Tests for the structured-record loader and chunk builders.

Pure-function tests (no OpenAI / DB needed). Run with pytest, or standalone:

    venv/Scripts/python.exe tests/test_record_loader.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make ``src`` importable when run without an installed package / pytest rootdir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rag.record_loader import (  # noqa: E402
    MAINTENANCE_RECORDS_PER_EQUIPMENT,
    RecordParseError,
    build_failure_chunks,
    build_maintenance_chunks,
    load_records,
)


def _failure_record(report_id: str = "FAR-1", equipment_id: str = "RMHP-001") -> dict:
    return {
        "report_id": report_id,
        "equipment_id": equipment_id,
        "equipment_name": "Wagon Tippler",
        "date_of_failure": "2024-08-05",
        "report_date": "2024-08-15",
        "title": "Tipping mechanism jam",
        "failure_description": "Tipping mechanism jammed during operation.",
        "symptoms_observed": ["Increased motor current", "Reduced throughput"],
        "root_cause_analysis": {
            "identified_root_cause": "Bearing wear/failure",
            "five_why_chain": ["Why? Jam.", "Why? Bearing wear."],
            "contributing_factors": ["Operator error"],
        },
        "corrective_actions": {
            "immediate": "Cleared the jam.",
            "long_term": "Add condition monitoring sensor.",
        },
        "status": "Closed - CAPA verified effective",
    }


def _maint_record(record_id: str, equipment_id: str, date: str, na: bool = False) -> dict:
    if na:
        return {
            "record_id": record_id,
            "equipment_id": equipment_id,
            "maintenance_date": date,
            "maintenance_type": "Preventive",
            "failure_mode_addressed": "N/A - scheduled preventive maintenance",
            "root_cause": "N/A - routine schedule per SOP",
            "corrective_action": "N/A",
            "parts_replaced": "Bolt torque check",
        }
    return {
        "record_id": record_id,
        "equipment_id": equipment_id,
        "maintenance_date": date,
        "maintenance_type": "Corrective (Breakdown)",
        "failure_mode_addressed": "Hydraulic seal leakage",
        "root_cause": "Sensor/instrument drift",
        "corrective_action": "Cleared blockage and inspected chute",
        "parts_replaced": "Hydraulic filter; Seal kit",
    }


# ---------------------------------------------------------------------------
# load_records
# ---------------------------------------------------------------------------
def test_load_json_list():
    raw = json.dumps([_failure_record()]).encode("utf-8")
    records = load_records(raw, "failure_analysis_reports.json", "FAILURE_REPORT")
    assert len(records) == 1
    assert records[0]["equipment_id"] == "RMHP-001"


def test_load_csv():
    raw = (
        "record_id,equipment_id,maintenance_date,corrective_action\n"
        "MNT-1,RMHP-001,2024-01-05,Cleared blockage\n"
    ).encode("utf-8")
    records = load_records(raw, "maintenance_history.csv", "MAINTENANCE_LOG")
    assert len(records) == 1
    assert records[0]["equipment_id"] == "RMHP-001"


def test_load_records_missing_equipment_id_raises():
    raw = json.dumps([{"report_id": "X"}]).encode("utf-8")
    try:
        load_records(raw, "x.json", "FAILURE_REPORT")
    except RecordParseError:
        return
    raise AssertionError("expected RecordParseError for missing equipment_id")


def test_load_records_unsupported_extension_raises():
    try:
        load_records(b"x", "data.xlsx", "FAILURE_REPORT")
    except RecordParseError:
        return
    raise AssertionError("expected RecordParseError for unsupported extension")


# ---------------------------------------------------------------------------
# build_failure_chunks
# ---------------------------------------------------------------------------
def test_failure_three_facets_share_ref_and_payload():
    res = build_failure_chunks([_failure_record()], document_id="doc-1", valid_equipment=None)
    # 3 facet embeddings, 1 structured incident.
    assert len(res.entries) == 3
    assert len(res.incidents) == 1

    ref_ids = {payload["ref_id"] for _, payload in res.entries}
    assert len(ref_ids) == 1  # shared ref_id -> retrieval dedup
    assert ref_ids == {res.incidents[0].id}

    # All facets store the same full-record payload text incl. corrective actions.
    texts = {payload["text"] for _, payload in res.entries}
    assert len(texts) == 1
    full_text = texts.pop()
    assert "condition monitoring sensor" in full_text  # long-term action rode along
    facets = {payload["facet"] for _, payload in res.entries}
    assert facets == {"SYMPTOMS", "FAILURE_DESCRIPTION", "ROOT_CAUSE"}


def test_failure_event_date_metadata():
    res = build_failure_chunks([_failure_record()], document_id="doc-1", valid_equipment=None)
    _, payload = res.entries[0]
    assert payload["event_date"] == "2024-08-05"  # date_of_failure, not ingestion date
    assert payload["created_at"].startswith("2024-08-05")
    assert res.incidents[0].created_at == datetime(2024, 8, 5, tzinfo=timezone.utc)


def test_failure_unknown_equipment_filtered():
    records = [_failure_record(equipment_id="GOOD"), _failure_record(equipment_id="BAD")]
    res = build_failure_chunks(records, document_id="doc-1", valid_equipment={"GOOD"})
    assert len(res.incidents) == 1
    assert res.incidents[0].equipment_id == "GOOD"
    assert res.stats["skipped_unknown"] == 1


# ---------------------------------------------------------------------------
# build_maintenance_chunks
# ---------------------------------------------------------------------------
def test_maintenance_skips_routine_na():
    records = [
        _maint_record("MNT-1", "RMHP-001", "2024-01-05"),
        _maint_record("MNT-2", "RMHP-001", "2024-01-06", na=True),
    ]
    res = build_maintenance_chunks(records, document_id="doc-1", valid_equipment=None)
    assert len(res.logs) == 1
    assert len(res.entries) == 1
    assert res.stats["skipped_na"] == 1


def test_maintenance_keeps_latest_n_per_equipment():
    # 15 dated records for one equipment; only the latest 10 should survive.
    records = [
        _maint_record(f"MNT-{i:02d}", "RMHP-001", f"2024-02-{i:02d}")
        for i in range(1, 16)
    ]
    res = build_maintenance_chunks(records, document_id="doc-1", valid_equipment=None)
    assert len(res.entries) == MAINTENANCE_RECORDS_PER_EQUIPMENT == 10
    # The kept records must be the most recent ones (Feb 6..15).
    kept_dates = sorted(log.created_at for log in res.logs)
    assert kept_dates[0] == datetime(2024, 2, 6, tzinfo=timezone.utc)
    assert kept_dates[-1] == datetime(2024, 2, 15, tzinfo=timezone.utc)


def test_maintenance_event_date_metadata():
    res = build_maintenance_chunks(
        [_maint_record("MNT-1", "RMHP-001", "2024-01-05")],
        document_id="doc-1",
        valid_equipment=None,
    )
    _, payload = res.entries[0]
    assert payload["event_date"] == "2024-01-05"
    assert payload["created_at"].startswith("2024-01-05")
    assert payload["document_type"] == "MAINTENANCE_LOG"


def test_maintenance_latest_n_is_per_equipment():
    records = (
        [_maint_record(f"A-{i:02d}", "EQ-A", f"2024-03-{i:02d}") for i in range(1, 13)]
        + [_maint_record(f"B-{i:02d}", "EQ-B", f"2024-03-{i:02d}") for i in range(1, 4)]
    )
    res = build_maintenance_chunks(records, document_id="doc-1", valid_equipment=None)
    per_eq: dict[str, int] = {}
    for log in res.logs:
        per_eq[log.equipment_id] = per_eq.get(log.equipment_id, 0) + 1
    assert per_eq["EQ-A"] == 10  # capped
    assert per_eq["EQ-B"] == 3   # under the cap, all kept


def _run_standalone() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL {test.__name__}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
