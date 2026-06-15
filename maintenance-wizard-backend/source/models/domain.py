"""Domain models representing database rows.

These are lightweight ``dataclasses`` used internally by repositories and
services. They are distinct from the Pydantic schemas in ``schemas/``,
which are used for API request/response validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class Plant:
    id: str
    name: str
    location: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_row(cls, row: Any) -> "Plant":
        return cls(
            id=row["id"],
            name=row["name"],
            location=row["location"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class Equipment:
    id: str
    plant_id: str | None = None
    equipment_code: str | None = None
    equipment_name: str | None = None
    equipment_type: str | None = None
    manufacturer: str | None = None
    model_number: str | None = None
    installation_date: date | None = None
    expected_life_days: int | None = None
    criticality: str | None = None
    location_in_plant: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_row(cls, row: Any) -> "Equipment":
        return cls(
            id=row["id"],
            plant_id=row["plant_id"],
            equipment_code=row["equipment_code"],
            equipment_name=row["equipment_name"],
            equipment_type=row["equipment_type"],
            manufacturer=row["manufacturer"],
            model_number=row["model_number"],
            installation_date=row["installation_date"],
            expected_life_days=row["expected_life_days"],
            criticality=row["criticality"],
            location_in_plant=row["location_in_plant"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class Sensor:
    id: str
    sensor_code: str | None = None
    equipment_id: str | None = None
    sensor_name: str | None = None
    sensor_type: str | None = None
    unit: str | None = None
    min_threshold: float | None = None
    max_threshold: float | None = None
    warning_threshold: float | None = None
    critical_threshold: float | None = None
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: Any) -> "Sensor":
        return cls(
            id=row["id"],
            sensor_code=row["sensor_code"],
            equipment_id=row["equipment_id"],
            sensor_name=row["sensor_name"],
            sensor_type=row["sensor_type"],
            unit=row["unit"],
            min_threshold=row["min_threshold"],
            max_threshold=row["max_threshold"],
            warning_threshold=row["warning_threshold"],
            critical_threshold=row["critical_threshold"],
            created_at=row["created_at"],
        )


@dataclass
class SensorReading:
    id: str
    equipment_id: str | None = None
    sensor_id: str | None = None
    sensor_code: str | None = None
    value: float | None = None
    reading_timestamp: datetime | None = None
    ingestion_timestamp: datetime | None = None

    @classmethod
    def from_row(cls, row: Any) -> "SensorReading":
        return cls(
            id=row["id"],
            equipment_id=row["equipment_id"],
            sensor_id=row["sensor_id"],
            sensor_code=row["sensor_code"],
            value=row["value"],
            reading_timestamp=row["reading_timestamp"],
            ingestion_timestamp=row["ingestion_timestamp"],
        )


@dataclass
class EquipmentHealthRecord:
    id: str
    equipment_id: str | None = None
    health_score: int | None = None
    risk_level: str | None = None
    rul_days: int | None = None
    failure_probability: float | None = None
    predicted_failure: str | None = None
    preventive_actions_json: str | None = None
    expected_end_of_life_date: date | None = None
    is_active: bool = True
    generated_at: datetime | None = None
    agent_report_json: str | None = None

    @classmethod
    def from_row(cls, row: Any) -> "EquipmentHealthRecord":
        keys = row.keys()
        return cls(
            id=row["id"],
            equipment_id=row["equipment_id"],
            health_score=row["health_score"],
            risk_level=row["risk_level"],
            rul_days=row["rul_days"],
            failure_probability=row["failure_probability"],
            predicted_failure=row["predicted_failure"],
            preventive_actions_json=row["preventive_actions_json"],
            expected_end_of_life_date=row["expected_end_of_life_date"],
            is_active=bool(row["is_active"]),
            generated_at=row["generated_at"],
            agent_report_json=row["agent_report_json"] if "agent_report_json" in keys else None,
        )


@dataclass
class KnowledgeDocument:
    id: str
    equipment_id: str | None = None
    document_name: str | None = None
    document_type: str | None = None
    file_path: str | None = None
    file_hash: str | None = None
    uploaded_at: datetime | None = None

    @classmethod
    def from_row(cls, row: Any) -> "KnowledgeDocument":
        return cls(
            id=row["id"],
            equipment_id=row["equipment_id"],
            document_name=row["document_name"],
            document_type=row["document_type"],
            file_path=row["file_path"],
            file_hash=row["file_hash"],
            uploaded_at=row["uploaded_at"],
        )


@dataclass
class AgentSession:
    session_id: str
    user_id: str | None = None
    created_at: datetime | None = None
    last_updated_at: datetime | None = None

    @classmethod
    def from_row(cls, row: Any) -> "AgentSession":
        return cls(
            session_id=row["session_id"],
            user_id=row["user_id"],
            created_at=row["created_at"],
            last_updated_at=row["last_updated_at"],
        )


@dataclass
class AgentMemory:
    id: str
    equipment_id: str | None = None
    interaction_type: str | None = None
    user_query: str | None = None
    agent_response: str | None = None
    outcome: str | None = None
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: Any) -> "AgentMemory":
        return cls(
            id=row["id"],
            equipment_id=row["equipment_id"],
            interaction_type=row["interaction_type"],
            user_query=row["user_query"],
            agent_response=row["agent_response"],
            outcome=row["outcome"],
            created_at=row["created_at"],
        )
