"""API routes for agent (conversation / diagnosis) endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.deps import get_agent_service
from schemas.agent import AgentChatRequest
from services.agent_service import AgentService, EquipmentNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agent"])

# How often to emit a keep-alive while the (potentially long) agent runs, so the
# UI's connection does not time out waiting for the final answer.
_HEARTBEAT_SECONDS = 5.0


def _sse(event: str, data: dict) -> str:
    """Format a single Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/agent/chat")
async def agent_chat(
    request: AgentChatRequest,
    service: AgentService = Depends(get_agent_service),
) -> StreamingResponse:
    """Single conversational interface (_04_Agent.md), streamed over SSE.

    The engineer selects the equipment up front (``equipmentCode`` mandatory), so
    the orchestrator skips equipment resolution/confirmation and routes by intent
    to the General Knowledge, Equipment Knowledge, or multi-step Diagnosis agent —
    all grounded with live equipment data (health, sensors, anomaly alerts, fault
    messages, spares).

    Because a turn can take a while, the endpoint streams ``heartbeat`` events
    every 5 seconds until the answer is ready, then a final ``message`` event with
    the :class:`AgentChatResponse` payload (camelCase). Errors arrive as an
    ``error`` event.
    """

    async def event_stream():
        task = asyncio.create_task(service.chat(request))
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=_HEARTBEAT_SECONDS)
                if task in done:
                    break
                yield _sse("heartbeat", {"ts": datetime.now(timezone.utc).isoformat()})
            result = task.result()  # re-raises any error from service.chat
            yield _sse("message", result.model_dump())
        except EquipmentNotFoundError as exc:
            yield _sse("error", {"detail": str(exc), "equipment_code": exc.equipment_code})
        except Exception:  # pragma: no cover - defensive
            logger.exception("Agent chat failed")
            if not task.done():
                task.cancel()
            yield _sse("error", {"detail": "Internal error while generating the answer."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering so events flush live
        },
    )
