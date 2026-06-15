"""Sensor-driven predictive-maintenance engine (daily-aggregated schema).

Turns daily-aggregated sensor history into the structured health signals the
problem statement asks for — health score, abnormality detection, failure
criticality, remaining-useful-life (days to failure), a probable failure mode,
and prioritized preventive actions — for one piece of equipment.

Design choices
--------------
* **Deterministic and offline.** This is condition monitoring, not generation:
  it runs over *every* equipment on a schedule, must be cheap, and its outputs
  must be explainable and traceable to the sensor evidence. The agentic layer
  (which uses an LLM) consumes these records downstream and enriches the
  flagged equipment with a narrative report.
* **Status-flag driven.** The ``sensor`` table (and its per-channel thresholds)
  is no longer populated; instead each daily ``sensor_reading`` row carries a
  pre-computed ``status_flag`` (Normal / Warning / Critical). Channel health is
  derived from the recent fraction of Warning/Critical days plus the latest
  day's status, complemented by an age/wear-out lens.
* **Two complementary lenses on remaining life.** An *age* lens uses installation
  date vs. expected service life (long-term, wear-out), and a *condition* lens
  scales the remaining horizon by current health. RUL is the more pessimistic of
  the two, which is the safe choice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from models.domain import Equipment

# How much history to consider and what counts as "recent".
_MAX_HISTORY_DAYS = 30.0
_MAX_RUL_DAYS = 3650

_STATUS_RANK = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}
_RISK_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
_RISK_BY_RANK = {v: k for k, v in _RISK_RANK.items()}

# Normalisation of the textual ``status_flag`` to the internal status vocabulary.
_FLAG_TO_STATUS = {"normal": "NORMAL", "warning": "WARNING", "critical": "CRITICAL"}


@dataclass
class SensorAnalysis:
    """Per-channel analysis result (the explainable evidence behind a score)."""

    sensor_name: str
    sensor_type: str | None
    count: int
    latest_value: float | None
    latest_status: str            # NORMAL | WARNING | CRITICAL
    mean: float | None
    minimum: float | None
    maximum: float | None
    pct_warning: float            # fraction of days flagged Warning+
    pct_critical: float           # fraction of days flagged Critical
    slope_per_day: float          # least-squares trend of avg_value vs. day
    status: str                   # NORMAL | WARNING | CRITICAL
    health: float                 # 0..1, 1 == perfectly healthy
    rising: bool                  # avg_value trending upward materially
    symptom: str | None           # human-readable abnormality, None if normal

    @property
    def is_abnormal(self) -> bool:
        return self.status != "NORMAL"


@dataclass
class HealthPrediction:
    """Aggregated equipment-level prediction, ready to persist."""

    equipment_id: str
    health_score: int
    risk_level: str
    rul_days: int
    failure_probability: float
    predicted_failure: str
    preventive_actions: list[dict[str, Any]]
    expected_end_of_life_date: date | None
    abnormal_symptoms: list[str] = field(default_factory=list)
    sensor_analyses: list[SensorAnalysis] = field(default_factory=list)
    generated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Failure-mode knowledge map
# ---------------------------------------------------------------------------
# Maps a set of abnormal sensor *types* to a probable failure mode and a
# prioritized corrective/preventive action template. Rules are evaluated most-
# specific-first so a vibration+temperature combination resolves to bearing wear
# rather than to either single-channel rule.
_FAILURE_RULES: list[tuple[frozenset[str], str, list[str]]] = [
    (
        frozenset({"VIBRATION", "TEMP"}),
        "Bearing wear or shaft misalignment",
        [
            "Inspect and re-lubricate bearings; check for contamination",
            "Verify shaft alignment and coupling condition",
            "Measure bearing clearance; schedule bearing replacement if out of spec",
            "Trend vibration and temperature together until stabilised",
        ],
    ),
    (
        frozenset({"TEMP", "CURRENT"}),
        "Overload-induced overheating (cooling or lubrication deficiency)",
        [
            "Reduce load and verify duty cycle against rating",
            "Inspect cooling fans/ducts and lubrication system",
            "Check for blocked filters and ambient heat sources",
            "Thermography scan of windings and terminals",
        ],
    ),
    (
        frozenset({"VIBRATION"}),
        "Mechanical imbalance or bearing degradation",
        [
            "Perform vibration spectrum analysis to localise the source",
            "Inspect mounting bolts and foundation for looseness",
            "Balance rotating assembly; inspect bearings",
        ],
    ),
    (
        frozenset({"TEMP"}),
        "Overheating from cooling or lubrication issue",
        [
            "Inspect lubrication level and quality",
            "Verify cooling system and airflow",
            "Reduce load until temperature normalises",
        ],
    ),
    (
        frozenset({"CURRENT"}),
        "Electrical overload or winding insulation degradation",
        [
            "Measure insulation resistance and winding balance",
            "Inspect terminals/connections for heating",
            "Verify load and protection-relay settings",
        ],
    ),
    (
        frozenset({"PRESSURE"}),
        "Flow restriction or seal/valve degradation",
        [
            "Inspect for blockage, fouling or seal leakage",
            "Verify valve operation and set-points",
            "Check suction/discharge lines for restriction",
        ],
    ),
    (
        frozenset({"RPM"}),
        "Drive transmission fault (belt slippage or speed-control)",
        [
            "Inspect belts/couplings for slippage and wear",
            "Verify drive/VFD speed-control calibration",
            "Check load coupling and gearbox condition",
        ],
    ),
]
_DEFAULT_FAILURE = (
    "General performance degradation",
    [
        "Carry out a full condition inspection",
        "Review recent maintenance and operating history",
        "Increase monitoring frequency until the trend stabilises",
    ],
)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except (ValueError, TypeError):
        return None


def _infer_type(sensor_name: str) -> str | None:
    """Infer a coarse sensor type from the channel name (no ``sensor`` table)."""
    n = (sensor_name or "").lower()
    if "vibration" in n:
        return "VIBRATION"
    if "temp" in n:
        return "TEMP"
    if "pressure" in n:
        return "PRESSURE"
    if "current" in n or "load" in n or "torque" in n:
        return "CURRENT"
    if "rpm" in n or "speed" in n or "frequency" in n or "slew" in n:
        return "RPM"
    return None


def _normalise_flag(flag: Any) -> str:
    return _FLAG_TO_STATUS.get(str(flag or "").strip().lower(), "NORMAL")


def _slope_per_day(values: list[float]) -> float:
    """Least-squares slope of value vs. day index (one point per day)."""
    n = len(values)
    if n < 3:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    num = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n))
    return num / denom


def analyze_sensor(sensor_name: str, rows: list[dict[str, Any]]) -> SensorAnalysis | None:
    """Analyse one channel's recent daily history into a :class:`SensorAnalysis`.

    ``rows`` are ``sensor_reading`` dicts for a single ``sensor_name``, assumed
    ordered oldest-first by date.
    """
    if not rows:
        return None
    avgs = [float(r["avg_value"]) for r in rows if r.get("avg_value") is not None]
    if not avgs:
        return None
    statuses = [_normalise_flag(r.get("status_flag")) for r in rows]
    n = len(rows)

    pct_critical = sum(1 for s in statuses if s == "CRITICAL") / n
    pct_warning = sum(1 for s in statuses if s in ("WARNING", "CRITICAL")) / n
    latest_status = statuses[-1]

    maxima = [float(r["max_value"]) for r in rows if r.get("max_value") is not None]
    minima = [float(r["min_value"]) for r in rows if r.get("min_value") is not None]
    mean = sum(avgs) / len(avgs)
    slope = _slope_per_day(avgs)
    scale = max(abs(mean), 1e-6)
    rising = slope > 0 and (slope / scale) > 0.02

    # Channel status: latest day dominates, escalated by the recent breach rate.
    if latest_status == "CRITICAL" or pct_critical > 0.02:
        status = "CRITICAL"
    elif latest_status == "WARNING" or pct_warning > 0.10:
        status = "WARNING"
    else:
        status = "NORMAL"

    # Channel health from breach history, latest status and adverse trend.
    health = 1.0 - 0.6 * pct_critical - 0.25 * pct_warning
    if latest_status == "CRITICAL":
        health = min(health, 0.25)
    elif latest_status == "WARNING":
        health = min(health, 0.6)
    if rising and status != "NORMAL":
        health -= 0.1
    health = _clamp(health)

    symptom = _symptom(sensor_name, status, rows[-1], rising) if status != "NORMAL" else None

    return SensorAnalysis(
        sensor_name=sensor_name,
        sensor_type=_infer_type(sensor_name),
        count=n,
        latest_value=round(avgs[-1], 3),
        latest_status=latest_status,
        mean=round(mean, 3),
        minimum=round(min(minima), 3) if minima else None,
        maximum=round(max(maxima), 3) if maxima else None,
        pct_warning=round(pct_warning, 3),
        pct_critical=round(pct_critical, 3),
        slope_per_day=round(slope, 5),
        status=status,
        health=round(health, 3),
        rising=rising,
        symptom=symptom,
    )


def _symptom(sensor_name: str, status: str, latest_row: dict[str, Any], rising: bool) -> str:
    latest = latest_row.get("avg_value")
    trend = ", rising" if rising else ""
    label = sensor_name
    if status == "CRITICAL":
        return f"{label} critical (latest avg {latest}{trend})"
    return f"{label} warning (latest avg {latest}{trend})"


def predict_health(
    equipment: Equipment,
    readings: list[dict[str, Any]],
    now: datetime | None = None,
) -> HealthPrediction:
    """Compute a full :class:`HealthPrediction` for one equipment from daily readings."""
    now = now or datetime.now(timezone.utc)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in readings:
        name = r.get("sensor_name")
        if name:
            grouped.setdefault(name, []).append(r)

    analyses: list[SensorAnalysis] = []
    for name, rows in grouped.items():
        analysis = analyze_sensor(name, rows)
        if analysis is not None:
            analyses.append(analysis)

    age_days, expected_eol = _age_and_eol(equipment, now)

    if not analyses:
        return _age_only_prediction(equipment, age_days, expected_eol, now)

    healths = [a.health for a in analyses]
    min_health = min(healths)
    mean_health = sum(healths) / len(healths)
    condition = 0.6 * min_health + 0.4 * mean_health

    age_frac = _clamp(age_days / equipment.expected_life_days) if equipment.expected_life_days else 0.0
    health_score = int(round(_clamp(condition - 0.15 * age_frac) * 100))
    health_score = max(1, min(100, health_score))

    worst_status = max((a.status for a in analyses), key=lambda s: _STATUS_RANK[s])

    # Keep the score coherent with the worst channel status: a single channel
    # that is currently CRITICAL/WARNING should cap overall health regardless of
    # how healthy the averaged condition looks, so score and risk never
    # contradict each other (a 96/CRITICAL record would be misleading).
    if worst_status == "CRITICAL":
        health_score = min(health_score, 55)
    elif worst_status == "WARNING":
        health_score = min(health_score, 80)
    health_score = max(1, health_score)
    abnormal = sorted(
        (a for a in analyses if a.is_abnormal),
        key=lambda a: (_STATUS_RANK[a.status], a.pct_critical),
        reverse=True,
    )

    risk_level = _risk_level(health_score, worst_status, abnormal, equipment.criticality)
    failure_probability = _failure_probability(health_score, analyses)
    rul_days = _remaining_useful_life(health_score, age_days, equipment, risk_level)
    predicted_failure, preventive_actions = _failure_mode_and_actions(abnormal, risk_level, equipment)
    abnormal_symptoms = [a.symptom for a in abnormal if a.symptom]

    return HealthPrediction(
        equipment_id=equipment.id,
        health_score=health_score,
        risk_level=risk_level,
        rul_days=rul_days,
        failure_probability=failure_probability,
        predicted_failure=predicted_failure,
        preventive_actions=preventive_actions,
        expected_end_of_life_date=expected_eol,
        abnormal_symptoms=abnormal_symptoms,
        sensor_analyses=analyses,
        generated_at=now,
    )


def _age_and_eol(equipment: Equipment, now: datetime) -> tuple[float, date | None]:
    from datetime import timedelta

    install = _parse_date(equipment.installation_date)
    age_days = max(0.0, (now.date() - install).days) if install else 0.0
    eol: date | None = None
    if install and equipment.expected_life_days:
        eol = install + timedelta(days=int(equipment.expected_life_days))
    return age_days, eol


def _risk_level(
    health_score: int, worst_status: str, abnormal: list[SensorAnalysis], criticality: str | None
) -> str:
    has_critical = worst_status == "CRITICAL"
    rising_warning = any(a.status == "WARNING" and a.rising for a in abnormal)

    if has_critical or health_score < 40:
        rank = _RISK_RANK["CRITICAL"]
    elif health_score < 60 or rising_warning:
        rank = _RISK_RANK["HIGH"]
    elif health_score < 78 or abnormal:
        rank = _RISK_RANK["MEDIUM"]
    else:
        rank = _RISK_RANK["LOW"]

    # Bottleneck prioritisation: a business-critical asset that is already
    # degrading is escalated one notch. Never escalate a healthy LOW asset.
    if (criticality or "").upper() == "CRITICAL" and rank == _RISK_RANK["MEDIUM"]:
        rank = _RISK_RANK["HIGH"]

    return _RISK_BY_RANK[rank]


def _failure_probability(health_score: int, analyses: list[SensorAnalysis]) -> float:
    max_critical = max((a.pct_critical for a in analyses), default=0.0)
    max_warning = max((a.pct_warning for a in analyses), default=0.0)
    p = 0.55 * (1.0 - health_score / 100.0) + 0.30 * max_critical + 0.15 * max_warning
    return round(_clamp(p), 2)


def _remaining_useful_life(
    health_score: int, age_days: float, equipment: Equipment, risk_level: str
) -> int:
    if equipment.expected_life_days:
        age_rul = max(0.0, equipment.expected_life_days - age_days)
    else:
        age_rul = float(_MAX_RUL_DAYS)

    horizon = min(age_rul, float(_MAX_RUL_DAYS))
    health_rul = horizon * (health_score / 100.0)
    rul = min(age_rul, health_rul)
    # Floor for already-critical assets so RUL never reads as a comfortable
    # number when a channel is over its critical limit.
    if risk_level == "CRITICAL":
        rul = min(rul, 14.0)
    return int(max(0, round(rul)))


def _failure_mode_and_actions(
    abnormal: list[SensorAnalysis], risk_level: str, equipment: Equipment
) -> tuple[str, list[dict[str, Any]]]:
    if not abnormal:
        text = "No abnormality detected; equipment operating within normal limits"
        actions = [{"priority": 1, "action": "Continue routine condition monitoring"}]
        return text, actions

    abnormal_types = {a.sensor_type for a in abnormal if a.sensor_type}
    mode_text, action_templates = _match_failure_rule(abnormal_types)

    drivers = "; ".join(a.symptom for a in abnormal[:3] if a.symptom)
    predicted_failure = f"{mode_text} — driven by {drivers}" if drivers else mode_text

    actions: list[dict[str, Any]] = []
    priority = 1
    if risk_level in ("CRITICAL", "HIGH"):
        if risk_level == "CRITICAL":
            actions.append({
                "priority": priority,
                "action": f"URGENT: inspect {equipment.equipment_code or equipment.id} now; "
                          "consider controlled shutdown to prevent catastrophic failure",
            })
        else:
            actions.append({
                "priority": priority,
                "action": "Schedule priority inspection within the next operating shift",
            })
        priority += 1

    for template in action_templates:
        actions.append({"priority": priority, "action": template})
        priority += 1

    actions.append({"priority": priority, "action": "Re-run health prediction after corrective action to confirm recovery"})
    return predicted_failure, actions


def _match_failure_rule(abnormal_types: set[str]) -> tuple[str, list[str]]:
    best: tuple[frozenset[str], str, list[str]] | None = None
    for key, text, actions in _FAILURE_RULES:
        if key & abnormal_types:
            if best is None or len(key & abnormal_types) > len(best[0] & abnormal_types):
                best = (key, text, actions)
    if best is None:
        return _DEFAULT_FAILURE
    return best[1], best[2]


def _age_only_prediction(
    equipment: Equipment, age_days: float, expected_eol: date | None, now: datetime
) -> HealthPrediction:
    age_frac = _clamp(age_days / equipment.expected_life_days) if equipment.expected_life_days else 0.0
    health_score = max(1, int(round((1.0 - 0.6 * age_frac) * 100)))
    age_rul = int(max(0.0, equipment.expected_life_days - age_days)) if equipment.expected_life_days else _MAX_RUL_DAYS
    risk = "LOW" if age_frac < 0.6 else ("MEDIUM" if age_frac < 0.85 else "HIGH")
    return HealthPrediction(
        equipment_id=equipment.id,
        health_score=health_score,
        risk_level=risk,
        rul_days=age_rul,
        failure_probability=round(_clamp(0.5 * age_frac), 2),
        predicted_failure="No sensor data available; assessment based on service age only",
        preventive_actions=[
            {"priority": 1, "action": "Verify sensor connectivity and data ingestion for this equipment"},
            {"priority": 2, "action": "Perform a manual condition inspection"},
        ],
        expected_end_of_life_date=expected_eol,
        abnormal_symptoms=[],
        sensor_analyses=[],
        generated_at=now,
    )
