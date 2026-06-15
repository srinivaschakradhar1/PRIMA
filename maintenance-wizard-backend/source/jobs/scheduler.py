"""Background job scheduling using APScheduler.

Runs the sensor-driven health-prediction engine periodically so health scores,
risk levels, RUL and preventive actions in ``equipment_health_record`` stay
current as new sensor readings arrive.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# How often to run the agentic health refresh (triage + deep analysis of
# suspect equipment). Daily, since the deep pass calls the LLM per suspect.
_HEALTH_PREDICTION_INTERVAL_HOURS = 24
_HEALTH_PREDICTION_JOB_ID = "health_prediction_refresh"


def start_scheduler() -> None:
    """Start the background job scheduler."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Background job scheduler started.")


def schedule_health_predictions(db) -> None:
    """Register the recurring agentic health-refresh job (idempotent)."""
    from prediction.agentic_service import build_agentic_health_service

    service = build_agentic_health_service(db)

    async def _run() -> None:
        try:
            await service.refresh_all()
        except Exception:  # never let a job error kill the scheduler thread
            logger.exception("Scheduled agentic health refresh failed.")

    scheduler.add_job(
        _run,
        trigger="interval",
        hours=_HEALTH_PREDICTION_INTERVAL_HOURS,
        id=_HEALTH_PREDICTION_JOB_ID,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    logger.info(
        "Registered agentic health-refresh job (every %dh).",
        _HEALTH_PREDICTION_INTERVAL_HOURS,
    )


def shutdown_scheduler() -> None:
    """Shut down the background job scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background job scheduler shut down.")
