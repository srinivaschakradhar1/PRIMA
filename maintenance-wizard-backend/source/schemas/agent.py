"""Pydantic schemas for agent (conversation / diagnosis) endpoints."""

from __future__ import annotations

from pydantic import Field

from schemas.common import CamelModel


class ConversationMessage(CamelModel):
    """A single prior turn in the conversation history (_04_Agent.md §2)."""

    role: str
    content: str


class AgentChatRequest(CamelModel):
    """Request schema for POST /agent/chat (_04_Agent.md §2).

    The engineer always selects the equipment up front, so ``equipment_code`` is
    mandatory and the orchestrator no longer resolves or confirms equipment.
    ``conversation_history`` carries prior turns so follow-up questions stay in
    context.
    """

    session_id: str
    equipment_code: str
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    message: str


class Citation(CamelModel):
    """A citation referencing a source document."""

    document: str
    page: int | None = None


class AgentChatResponse(CamelModel):
    """Response schema for POST /agent/chat (_04_Agent.md §2).

    Streamed as the final ``message`` event of the SSE response. ``equipment_code``
    echoes the equipment the answer pertains to (always present now that the
    engineer selects it up front).
    """

    response: str
    equipment_code: str
    citations: list[Citation] = Field(default_factory=list)
    agent_trace_id: str


class AgentDiagnoseRequest(CamelModel):
    """Request schema for POST /agent/diagnose."""

    equipment_id: str
    symptoms: list[str] = Field(default_factory=list)


class RootCause(CamelModel):
    """A probable root cause with an associated confidence score."""

    cause: str
    confidence: float


class AgentDiagnoseResponse(CamelModel):
    """Response schema for POST /agent/diagnose."""

    diagnosis: str
    confidence: float
    root_causes: list[RootCause] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
