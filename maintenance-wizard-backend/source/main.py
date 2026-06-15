"""FastAPI application entry point.

AI-Powered Maintenance Wizard for Steel Plants - backend API.

Startup sequence (per technical design):
    Load JSON Files -> Populate SQLite Tables -> Initialize FAISS -> Start FastAPI
"""

from __future__ import annotations

import logging
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import asyncio

from api.agent import router as agent_router
from api.equipment import router as equipment_router
from api.exceptions import (
    NotFoundError,
    not_found_exception_handler,
    openai_unavailable_exception_handler,
)
from api.knowledge import router as knowledge_router
from api.plants import router as plants_router
from api.sensor_readings import router as sensor_readings_router
from database.connection import db
from jobs.scheduler import schedule_health_predictions, shutdown_scheduler, start_scheduler
from prediction.agentic_service import build_agentic_health_service
from rag.embeddings import embedding_client
from rag.errors import OpenAIUnavailableError
from rag.llm import llm_client
from startup.data_loader import initialize_database
from startup.logging_config import configure_logging
from vectorstore.faiss_index import initialize_faiss_index

configure_logging()
logger = logging.getLogger(__name__)


async def _verify_openai_connectivity() -> None:
    """Probe OpenAI (chat + embeddings) and abort startup if it is unreachable."""
    try:
        await asyncio.to_thread(llm_client.verify_connectivity)
        await asyncio.to_thread(embedding_client.verify_connectivity)
    except OpenAIUnavailableError as exc:
        logger.critical(
            "OpenAI connectivity check failed at startup; aborting. The RAG "
            "pipeline has no offline fallback. Reason: %s", exc
        )
        raise
    logger.info("OpenAI connectivity verified (chat + embeddings).")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up...")

    # 1. Connect to the database
    db.connect()

    # 2. Load data files and populate SQLite tables
    await initialize_database(db)

    # 3. Initialize FAISS
    initialize_faiss_index()

    # 3b. Verify OpenAI connectivity up front. The RAG pipeline has no offline
    #     fallback, so a misconfigured / unreachable key must fail loudly at
    #     startup rather than surfacing as silent low-quality results later.
    await _verify_openai_connectivity()

    # 4. Compute fresh health predictions (deterministic triage + agentic deep
    #    analysis of suspect equipment), superseding the seed health records,
    #    then start the background job that keeps them current.
    # try:
    #     await build_agentic_health_service(db).refresh_all()
    # except Exception:
    #     logger.exception("Initial agentic health refresh failed at startup.")
    start_scheduler()
    # schedule_health_predictions(db)

    logger.info("Application startup complete.")

    yield

    logger.info("Application shutting down...")
    shutdown_scheduler()
    db.close()
    logger.info("Application shutdown complete.")


app = FastAPI(
    title="AI-Powered Maintenance Wizard for Steel Plants",
    description="Backend API for the AI-Powered Maintenance Wizard.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(NotFoundError, not_found_exception_handler)
app.add_exception_handler(OpenAIUnavailableError, openai_unavailable_exception_handler)

app.include_router(plants_router)
app.include_router(equipment_router)
app.include_router(sensor_readings_router)
app.include_router(knowledge_router)
app.include_router(agent_router)


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Simple liveness check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",      # file_name:fastapi_app_variable
        host="0.0.0.0",
        port=8080,
        reload=True,     # remove in production
    )