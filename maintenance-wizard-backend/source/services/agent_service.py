"""Service layer for agent (conversation / diagnosis) endpoints.

* /agent/chat is the single conversational interface (_04_Agent.md). It is
  backed by the LangGraph conversation orchestrator, which detects intent,
  resolves equipment, and routes to the General / Equipment / Diagnosis agents.
* /agent/diagnose is the dedicated symptom-driven diagnosis endpoint, backed by
  the RAG search pipeline.

Both persist session and memory records. These endpoints require OpenAI; if it is
unavailable the request fails with ``OpenAIUnavailableError`` (HTTP 503) rather
than returning a silently degraded answer.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from agents.conversation import ConversationAgent
from models.domain import AgentMemory, AgentSession
from models.enums import InteractionType, Outcome
from rag.search import SearchPipeline
from repositories.agent_repository import AgentMemoryRepository, AgentSessionRepository
from repositories.equipment_repository import EquipmentRepository
from schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentDiagnoseRequest,
    AgentDiagnoseResponse,
    Citation,
    RootCause,
)

logger = logging.getLogger(__name__)


class EquipmentNotFoundError(Exception):
    """Raised when the mandatory equipment_code does not match any equipment."""

    def __init__(self, equipment_code: str) -> None:
        super().__init__(f"Unknown equipment_code: {equipment_code}")
        self.equipment_code = equipment_code


class AgentService:
    """Business logic for the maintenance conversation and diagnosis endpoints."""

    def __init__(
        self,
        session_repository: AgentSessionRepository,
        memory_repository: AgentMemoryRepository,
        equipment_repository: EquipmentRepository,
        search_pipeline: SearchPipeline,
        conversation_agent: ConversationAgent,
    ) -> None:
        self._session_repository = session_repository
        self._memory_repository = memory_repository
        self._equipment_repository = equipment_repository
        self._search = search_pipeline
        self._conversation_agent = conversation_agent

    async def chat(self, request: AgentChatRequest) -> AgentChatResponse:
        now = datetime.now(timezone.utc)

        # Equipment is mandatory and chosen by the engineer up front.
        if not await self._equipment_repository.exists(request.equipment_code):
            raise EquipmentNotFoundError(request.equipment_code)

        existing_session = await self._session_repository.get_by_id(request.session_id)
        session = AgentSession(
            session_id=request.session_id,
            user_id=None,
            created_at=existing_session.created_at if existing_session else now,
            last_updated_at=now,
        )
        await self._session_repository.upsert(session)

        # The conversation orchestrator owns intent detection, agent routing and
        # memory writes (equipment resolution/confirmation is no longer needed).
        final = await self._conversation_agent.chat(
            session_id=request.session_id,
            equipment_code=request.equipment_code,
            message=request.message,
            conversation_history=[m.model_dump() for m in request.conversation_history],
            agent_trace_id=str(uuid.uuid4()),
        )

        citations = [
            Citation(document=c.get("document", "unknown"), page=c.get("page"))
            for c in final.get("citations", [])
        ]
        return AgentChatResponse(
            response=final.get("response", ""),
            equipment_code=final.get("equipment_code") or request.equipment_code,
            citations=citations,
            agent_trace_id=final.get("agent_trace_id", str(uuid.uuid4())),
        )

    async def diagnose(self, request: AgentDiagnoseRequest) -> AgentDiagnoseResponse | None:
        if not await self._equipment_repository.exists(request.equipment_id):
            return None

        now = datetime.now(timezone.utc)
        result = await self._search.diagnose(request.equipment_id, request.symptoms)

        root_causes = [RootCause(cause=cause, confidence=conf) for cause, conf in result.root_causes]
        if not root_causes:
            root_causes = [RootCause(cause="No matching root cause found in knowledge base", confidence=0.0)]

        recommended_actions = result.recommended_actions or [
            "Insufficient indexed knowledge for this equipment; upload relevant "
            "failure reports, manuals and maintenance logs."
        ]

        await self._memory_repository.insert(
            AgentMemory(
                id=str(uuid.uuid4()),
                equipment_id=request.equipment_id,
                interaction_type=InteractionType.DIAGNOSIS.value,
                user_query=", ".join(request.symptoms),
                agent_response=result.answer,
                outcome=Outcome.PENDING.value,
                created_at=now,
            )
        )

        return AgentDiagnoseResponse(
            diagnosis=result.answer,
            confidence=result.confidence,
            root_causes=root_causes,
            recommended_actions=recommended_actions,
        )
