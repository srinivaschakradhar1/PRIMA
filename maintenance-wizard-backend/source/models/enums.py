"""Enumerations used across the application."""

from __future__ import annotations

from enum import Enum


class Criticality(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EquipmentStatus(str, Enum):
    UP = "UP"
    FAILED = "FAILED"
    SCHEDULED_DOWN = "SCHEDULED_DOWN"
    MAINTENANCE = "MAINTENANCE"


class SensorType(str, Enum):
    TEMP = "TEMP"
    VIBRATION = "VIBRATION"
    PRESSURE = "PRESSURE"
    RPM = "RPM"
    CURRENT = "CURRENT"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DocumentType(str, Enum):
    MANUAL = "MANUAL"
    SOP = "SOP"
    FAILURE_REPORT = "FAILURE_REPORT"
    MAINTENANCE_LOG = "MAINTENANCE_LOG"
    SPARE_PART = "SPARE_PART"


class InteractionType(str, Enum):
    CHAT = "CHAT"
    DIAGNOSIS = "DIAGNOSIS"
    FEEDBACK = "FEEDBACK"


class Outcome(str, Enum):
    DIAGNOSIS_CONFIRMED = "DIAGNOSIS_CONFIRMED"
    DIAGNOSIS_REJECTED = "DIAGNOSIS_REJECTED"
    ACTUAL_FAILURE_DISCOVERED = "ACTUAL_FAILURE_DISCOVERED"
    PENDING = "PENDING"
