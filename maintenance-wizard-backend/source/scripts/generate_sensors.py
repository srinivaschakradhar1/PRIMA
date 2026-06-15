"""One-off script to generate data/sensors.json.

Generates 50 sensors total across the 10 equipment items, with at least
three sensors per equipment, using sensor types appropriate to each
equipment type.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CREATED_AT = "2025-01-01T00:00:00"

# (sensor_type, unit, min, max, warning, critical, name_suffix)
SENSOR_TEMPLATES = {
    "TEMP": ("TEMP", "C", 0, 120, 85, 100, "Temperature"),
    "VIBRATION": ("VIBRATION", "mm/s", 0, 12, 6, 9, "Vibration"),
    "PRESSURE": ("PRESSURE", "bar", 0, 16, 12, 14, "Pressure"),
    "RPM": ("RPM", "rpm", 0, 2000, 1700, 1850, "RPM"),
    "CURRENT": ("CURRENT", "A", 0, 500, 400, 460, "Current"),
}

# equipment_id -> list of sensor type keys (>=3 each), totaling 50
EQUIPMENT_SENSOR_PLAN: dict[str, list[str]] = {
    "eq-001": ["TEMP", "VIBRATION", "CURRENT", "RPM", "PRESSURE"],
    "eq-002": ["TEMP", "VIBRATION", "PRESSURE", "CURRENT", "RPM"],
    "eq-003": ["TEMP", "VIBRATION", "CURRENT", "RPM", "PRESSURE"],
    "eq-004": ["TEMP", "VIBRATION", "RPM", "PRESSURE", "CURRENT"],
    "eq-005": ["TEMP", "VIBRATION", "CURRENT", "RPM", "PRESSURE"],
    "eq-006": ["TEMP", "PRESSURE", "VIBRATION", "CURRENT", "RPM"],
    "eq-007": ["TEMP", "VIBRATION", "PRESSURE", "CURRENT", "RPM"],
    "eq-008": ["VIBRATION", "CURRENT", "RPM", "TEMP", "PRESSURE"],
    "eq-009": ["TEMP", "CURRENT", "PRESSURE", "VIBRATION", "RPM"],
    "eq-010": ["TEMP", "PRESSURE", "VIBRATION", "CURRENT", "RPM"],
}

EQUIPMENT_CODE: dict[str, str] = {
    "eq-001": "BF-101",
    "eq-002": "BF-102",
    "eq-003": "RM-201",
    "eq-004": "RM-202",
    "eq-005": "CV-301",
    "eq-006": "AC-401",
    "eq-007": "CC-501",
    "eq-008": "CR-601",
    "eq-009": "EAF-701",
    "eq-010": "WTP-801",
}

EQUIPMENT_NAME: dict[str, str] = {
    "eq-001": "Blast Furnace Main Fan",
    "eq-002": "Blast Furnace Cooling Pump",
    "eq-003": "Rolling Mill Main Motor",
    "eq-004": "Rolling Mill Gearbox",
    "eq-005": "Sinter Plant Conveyor Belt",
    "eq-006": "Air Compressor Unit 1",
    "eq-007": "Continuous Casting Machine",
    "eq-008": "Overhead Crane 1",
    "eq-009": "Electric Arc Furnace Transformer",
    "eq-010": "Water Treatment Plant Pump",
}


def main() -> None:
    sensors: list[dict] = []
    sensor_counter = 1

    for equipment_id, sensor_types in EQUIPMENT_SENSOR_PLAN.items():
        code = EQUIPMENT_CODE[equipment_id]
        name = EQUIPMENT_NAME[equipment_id]

        for sensor_type in sensor_types:
            template = SENSOR_TEMPLATES[sensor_type]
            _, unit, min_t, max_t, warn_t, crit_t, suffix = template

            sensor_id = f"sen-{sensor_counter:03d}"
            sensor_code = f"{code}-{sensor_type}"

            sensors.append(
                {
                    "id": sensor_id,
                    "sensor_code": sensor_code,
                    "equipment_id": equipment_id,
                    "sensor_name": f"{name} {suffix}",
                    "sensor_type": sensor_type,
                    "unit": unit,
                    "min_threshold": min_t,
                    "max_threshold": max_t,
                    "warning_threshold": warn_t,
                    "critical_threshold": crit_t,
                    "created_at": CREATED_AT,
                }
            )
            sensor_counter += 1

    print(f"Total sensors generated: {len(sensors)}")
    assert len(sensors) == 50, f"Expected 50 sensors, got {len(sensors)}"

    for equipment_id, sensor_types in EQUIPMENT_SENSOR_PLAN.items():
        assert len(sensor_types) >= 3, f"{equipment_id} has fewer than 3 sensors"

    output_path = DATA_DIR / "sensors.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sensors, f, indent=2)

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
