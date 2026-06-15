"""Shared FastAPI dependencies for repositories and services."""

from __future__ import annotations

from agents.conversation import get_conversation_agent
from database.connection import db
from prediction.agentic_service import AgenticHealthService, build_agentic_health_service
from prediction.service import HealthPredictionService, build_health_prediction_service
from rag.ingestion import IngestionPipeline
from rag.search import SearchPipeline
from repositories.agent_repository import AgentMemoryRepository, AgentSessionRepository
from repositories.equipment_repository import EquipmentRepository
from repositories.health_repository import HealthRepository
from repositories.knowledge_repository import KnowledgeRepository
from repositories.plant_repository import PlantRepository
from repositories.rag_repository import RagRepository
from services.agent_service import AgentService
from services.equipment_service import EquipmentService
from services.knowledge_service import KnowledgeService
from services.plant_service import PlantService
from services.sensor_reading_service import SensorReadingService


def get_plant_service() -> PlantService:
    return PlantService(PlantRepository(db))


def get_equipment_service() -> EquipmentService:
    return EquipmentService(
        equipment_repository=EquipmentRepository(db),
        health_repository=HealthRepository(db),
    )


def get_sensor_reading_service() -> SensorReadingService:
    return SensorReadingService(equipment_repository=EquipmentRepository(db))


def get_health_prediction_service() -> HealthPredictionService:
    return build_health_prediction_service(db)


def get_agentic_health_service() -> AgenticHealthService:
    return build_agentic_health_service(db)


def get_knowledge_service() -> KnowledgeService:
    return KnowledgeService(
        knowledge_repository=KnowledgeRepository(db),
        equipment_repository=EquipmentRepository(db),
        ingestion_pipeline=IngestionPipeline(
            rag_repository=RagRepository(db),
            equipment_repository=EquipmentRepository(db),
        ),
    )


def get_agent_service() -> AgentService:
    return AgentService(
        session_repository=AgentSessionRepository(db),
        memory_repository=AgentMemoryRepository(db),
        equipment_repository=EquipmentRepository(db),
        search_pipeline=SearchPipeline(
            rag_repository=RagRepository(db),
            equipment_repository=EquipmentRepository(db),
            knowledge_repository=KnowledgeRepository(db),
        ),
        conversation_agent=get_conversation_agent(),
    )
