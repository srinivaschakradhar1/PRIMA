"""Generate data/sensor_readings.json.

Creates synthetic sensor reading records for every sensor defined in
data/sensors.json, covering a 2-day window at 5-minute intervals
(576 readings per sensor).

Values are generated around the midpoint of each sensor's normal
operating range, with random noise plus a small daily cyclical pattern.
For equipment in a degraded/failed/scheduled-down state, a drift toward
(or past) the warning/critical thresholds is layered in to make the
dataset realistic for anomaly detection and health scoring.

Usage:
    python scripts/generate_sensor_readings.py
"""

from __future__ import annotations

import json
import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

INTERVAL_MINUTES = 5
DAYS = 2
READINGS_PER_SENSOR = (DAYS * 24 * 60) // INTERVAL_MINUTES  # 576

# End time anchored to "now" (rounded down to the nearest 5 minutes), so the
# generated window always represents "the last 2 days".
def _round_down_to_interval(dt: datetime, minutes: int) -> datetime:
    discard = timedelta(
        minutes=dt.minute % minutes,
        seconds=dt.second,
        microseconds=dt.microsecond,
    )
    return dt - discard


END_TIME = _round_down_to_interval(datetime.now(timezone.utc), INTERVAL_MINUTES)
START_TIME = END_TIME - timedelta(days=DAYS)

# Equipment whose readings should trend toward/through warning or critical
# thresholds over the 2-day window, simulating degradation.
DEGRADING_EQUIPMENT = {
    "eq-003": "critical",  # FAILED - already past critical threshold by end
    "eq-002": "warning",   # MAINTENANCE - approaching warning threshold
    "eq-008": "warning",   # SCHEDULED_DOWN - approaching warning threshold
    "eq-007": "watch",     # HIGH risk - mild upward drift, within range
}


def _base_value(sensor: dict) -> float:
    """A sensible 'normal operating' baseline within [min, warning)."""
    min_t = sensor["min_threshold"]
    warn_t = sensor["warning_threshold"]
    span = warn_t - min_t
    # Sit around 55-70% of the way from min to warning threshold.
    return min_t + span * random.uniform(0.55, 0.70)


def _noise_amplitude(sensor: dict) -> float:
    span = sensor["max_threshold"] - sensor["min_threshold"]
    return span * 0.02  # 2% of full range as standard noise


def _generate_series(sensor: dict) -> list[float]:
    """Generate a series of READINGS_PER_SENSOR values for one sensor."""
    equipment_id = sensor["equipment_id"]
    base = _base_value(sensor)
    noise_amp = _noise_amplitude(sensor)
    min_t = sensor["min_threshold"]
    max_t = sensor["max_threshold"]
    warn_t = sensor["warning_threshold"]
    crit_t = sensor["critical_threshold"]

    degradation_mode = DEGRADING_EQUIPMENT.get(equipment_id)

    values: list[float] = []
    for i in range(READINGS_PER_SENSOR):
        progress = i / (READINGS_PER_SENSOR - 1)  # 0.0 -> 1.0 over the window

        # Mild daily cyclical pattern (load varies over a 24h cycle).
        cyclical = noise_amp * math.sin(2 * math.pi * (i / (24 * 60 / INTERVAL_MINUTES)))

        # Random noise.
        noise = random.gauss(0, noise_amp)

        # Drift component for degrading equipment.
        drift = 0.0
        if degradation_mode == "critical":
            # Ramp from baseline up past the critical threshold by end of window.
            target = crit_t + (max_t - crit_t) * 0.3
            drift = (target - base) * progress
        elif degradation_mode == "warning":
            # Ramp from baseline up to just past the warning threshold.
            target = warn_t + (crit_t - warn_t) * 0.4
            drift = (target - base) * progress
        elif degradation_mode == "watch":
            # Mild upward drift, staying below warning threshold.
            target = base + (warn_t - base) * 0.6
            drift = (target - base) * progress

        value = base + cyclical + noise + drift
        value = max(min_t, min(max_t * 1.05, value))  # allow slight overshoot past max
        values.append(round(value, 2))

    return values


def main() -> None:
    random.seed(42)

    sensors_path = DATA_DIR / "sensors.json"
    with open(sensors_path, "r", encoding="utf-8") as f:
        sensors = json.load(f)

    readings: list[dict] = []

    for sensor in sensors:
        series = _generate_series(sensor)

        for i, value in enumerate(series):
            reading_time = START_TIME + timedelta(minutes=INTERVAL_MINUTES * i)
            ingestion_time = reading_time + timedelta(seconds=5)

            readings.append(
                {
                    "id": f"sr-{uuid.uuid4()}",
                    "equipment_id": sensor["equipment_id"],
                    "sensor_id": sensor["id"],
                    "sensor_code": sensor["sensor_code"],
                    "value": value,
                    "reading_timestamp": reading_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "ingestion_timestamp": ingestion_time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            )

    print(f"Sensors: {len(sensors)}")
    print(f"Readings per sensor: {READINGS_PER_SENSOR}")
    print(f"Total readings: {len(readings)}")
    print(f"Window: {START_TIME.isoformat()} -> {END_TIME.isoformat()}")

    output_path = DATA_DIR / "sensor_readings.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(readings, f, indent=2)

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
