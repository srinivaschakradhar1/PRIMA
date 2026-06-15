"""LangGraph state definitions for the conversation and diagnosis graphs.

These are ``TypedDict`` schemas. LangGraph shallow-merges the partial dict each
node returns into the running state, so nodes only need to return the keys they
produce.
"""

from __future__ import annotations

from typing import Any, TypedDict


class ConversationState(TypedDict, total=False):
    """State threaded through the conversation orchestrator (_04_Agent.md §21)."""

    # --- Inputs ---------------------------------------------------------
    session_id: str
    user_id: str
    message: str
    conversation_history: list[dict[str, str]]

    # --- Scope guardrail ------------------------------------------------
    blocked: bool

    # --- Context builder ------------------------------------------------
    is_affirmation: bool
    history_equipment_code: str | None

    # --- Co-occurring-symptom probe -------------------------------------
    awaiting_symptom_confirmation: bool

    # --- Intent detection -----------------------------------------------
    intent: str
    intent_confidence: float

    # --- Equipment resolution -------------------------------------------
    equipment_id: str | None
    equipment_code: str | None
    equipment_type: str | None
    equipment_name: str | None
    equipment_confidence: float
    equipment_match: str | None  # "exact" | "fuzzy" | "context" | None

    # --- Routing / confirmation -----------------------------------------
    route: str
    requires_confirmation: bool

    # --- Outputs --------------------------------------------------------
    response: str
    citations: list[dict[str, Any]]
    diagnosis: dict[str, Any] | None
    agent_trace_id: str


class DiagnosisState(TypedDict, total=False):
    """State threaded through the multi-step diagnosis graph (_04_Agent.md §17)."""

    # --- Inputs ---------------------------------------------------------
    equipment_id: str | None
    equipment_code: str | None
    equipment_type: str | None
    equipment_name: str | None
    symptoms: list[str]
    question: str

    # --- Retrieval ------------------------------------------------------
    sensor_summary: dict[str, Any]
    health: dict[str, Any] | None
    incidents: list[dict[str, Any]]
    memory_hits: list[dict[str, Any]]
    anomalies: list[dict[str, Any]]             # recent anomaly_alert rows
    faults: list[dict[str, Any]]                # recent fault_error_message rows
    delays: list[dict[str, Any]]                # recent equipment_delay_log rows
    spares: list[dict[str, Any]]                # spare_parts_inventory rows

    # --- Reasoning ------------------------------------------------------
    hypotheses: list[dict[str, Any]]            # [{cause, confidence}]
    evidence: dict[str, list[dict[str, Any]]]   # cause -> [evidence...]
    validations: dict[str, dict[str, Any]]      # cause -> validation result
    scores: dict[str, dict[str, float]]         # cause -> score breakdown
    ranked: list[dict[str, Any]]                # [{cause, score, ...}] desc

    # --- Synthesis ------------------------------------------------------
    diagnosis: str
    confidence: float
    alternative_causes: list[dict[str, Any]]
    evidence_summary: list[dict[str, str]]
    recommendations: dict[str, list[str]]
    spare_parts_needed: list[dict[str, Any]]    # [{part, stock_status, lead_time_days}]
    days_to_shutdown: str                       # narrative remaining-life estimate
    citations: list[dict[str, Any]]

    # --- Final report composition ---------------------------------------
    report_markdown: str                        # templated, human-readable report
