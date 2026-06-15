"""Repositories for ``agent_session`` and ``agent_memory`` tables."""

from __future__ import annotations

from database.connection import Database
from models.domain import AgentMemory, AgentSession


class AgentSessionRepository:
    """Data access layer for agent session records."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_by_id(self, session_id: str) -> AgentSession | None:
        row = await self._db.fetch_one(
            "SELECT session_id, user_id, created_at, last_updated_at "
            "FROM agent_session WHERE session_id = ?",
            (session_id,),
        )
        return AgentSession.from_row(row) if row else None

    async def upsert(self, session: AgentSession) -> None:
        existing = await self.get_by_id(session.session_id)
        if existing is None:
            await self._db.execute_and_commit(
                "INSERT INTO agent_session (session_id, user_id, created_at, last_updated_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    session.session_id,
                    session.user_id,
                    session.created_at,
                    session.last_updated_at,
                ),
            )
        else:
            await self._db.execute_and_commit(
                "UPDATE agent_session SET user_id = ?, last_updated_at = ? "
                "WHERE session_id = ?",
                (session.user_id, session.last_updated_at, session.session_id),
            )


class AgentMemoryRepository:
    """Data access layer for agent memory records."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def insert(self, memory: AgentMemory) -> None:
        await self._db.execute_and_commit(
            "INSERT INTO agent_memory "
            "(id, equipment_id, interaction_type, user_query, agent_response, outcome, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                memory.id,
                memory.equipment_id,
                memory.interaction_type,
                memory.user_query,
                memory.agent_response,
                memory.outcome,
                memory.created_at,
            ),
        )

    async def list_by_equipment(self, equipment_id: str) -> list[AgentMemory]:
        rows = await self._db.fetch_all(
            "SELECT id, equipment_id, interaction_type, user_query, agent_response, "
            "outcome, created_at FROM agent_memory WHERE equipment_id = ? "
            "ORDER BY created_at DESC",
            (equipment_id,),
        )
        return [AgentMemory.from_row(row) for row in rows]
