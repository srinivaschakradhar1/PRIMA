"""Common shared Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CamelModel(BaseModel):
    """Base model with sensible defaults for API schemas."""

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """Generic message response, e.g. for 404s."""

    message: str


class StatusResponse(BaseModel):
    """Generic status response, e.g. for delete operations."""

    status: str
