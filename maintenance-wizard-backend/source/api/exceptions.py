"""Custom exception types and handlers for API error responses."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from rag.errors import OpenAIUnavailableError

logger = logging.getLogger(__name__)


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


async def not_found_exception_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"message": exc.message})


async def openai_unavailable_exception_handler(
    request: Request, exc: OpenAIUnavailableError
) -> JSONResponse:
    """Surface OpenAI connectivity failures as 503 (no silent degradation)."""
    logger.error("OpenAI unavailable while handling %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={
            "message": "AI service is unavailable. Check OpenAI configuration and "
            "connectivity, then retry.",
            "detail": str(exc),
        },
    )
