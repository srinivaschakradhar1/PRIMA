"""Conversation orchestrator agent (_04_Agent.md §1-21).

A single LangGraph orchestrator backs ``POST /agent/chat``. The engineer selects
the equipment up front (``equipment_code`` is mandatory), so the orchestrator no
longer resolves or confirms equipment. It builds conversation context, detects
intent, routes to one of three specialized agents (General Knowledge / Equipment
Knowledge / multi-step Diagnosis), then writes memory and assembles the response.

    START -> context_builder -> intent_detection -> agent_router
          -> {general|equipment|diagnosis} -> memory_writer
          -> response_generator -> END

The General/Equipment agents reuse the RAG :class:`rag.search.SearchPipeline`,
now grounded with live equipment data (health, sensor status, anomaly alerts,
fault messages and spare-parts inventory) gathered through the shared
:class:`agents.tools.MaintenanceTools`. The Diagnosis agent delegates to the
multi-step :class:`agents.diagnosis.DiagnosisAgent`, which already consumes those
operational tools.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.diagnosis import DiagnosisAgent
from agents.guardrail import REFUSAL_MESSAGE, ScopeGuard
from agents.state import ConversationState
from agents.tools import MaintenanceTools
from models.domain import AgentMemory
from models.enums import InteractionType, Outcome
from rag.errors import OpenAIUnavailableError
from rag.llm import llm_client
from rag.search import SearchPipeline
from repositories.agent_repository import AgentMemoryRepository
from repositories.equipment_repository import EquipmentRepository
from repositories.knowledge_repository import KnowledgeRepository
from repositories.rag_repository import RagRepository

logger = logging.getLogger(__name__)

# Intents (_04_Agent.md §5).
INTENT_GENERAL = "GENERAL_PLANT_QUESTION"
INTENT_EQUIPMENT = "EQUIPMENT_QUESTION"
INTENT_DIAGNOSIS = "DIAGNOSIS_REQUEST"
INTENT_UNKNOWN = "UNKNOWN"
_INTENTS = {INTENT_GENERAL, INTENT_EQUIPMENT, INTENT_DIAGNOSIS, INTENT_UNKNOWN}

# Intents that require an equipment to be confirmed before answering (§7).
_EQUIPMENT_INTENTS = {INTENT_EQUIPMENT, INTENT_DIAGNOSIS}

_AFFIRMATIONS = {"yes", "yeah", "yep", "correct", "right", "confirm", "confirmed",
                 "that's right", "thats right", "ok", "okay", "sure", "yes please"}
_NEGATIONS = ("no", "nope", "incorrect", "wrong", "actually")

# Marker embedded in the co-occurring-symptom probe so the *next* turn can be
# recognised as the engineer's answer (the API is stateless — the only signal is
# the prior assistant message echoed back in conversation_history). Kept clear of
# the literal word "diagnosis" so the feedback heuristic in _maybe_write_feedback
# never misfires on the answer turn.
_SYMPTOM_PROBE_MARKER = "have you also noticed any of these"
# Cap on how many co-occurring symptoms we surface in a single probe.
_MAX_PROBE_SYMPTOMS = 5

# Diagnosis signals are symptom/problem oriented (a bare metric like
# "temperature" is not enough — "temperature is high/increasing" is).
_DIAGNOSIS_KEYWORDS = ("diagnos", "why is", "why does", "why did", "failing", "fault",
                       "overheat", "not working", "stopped", "abnormal", "increasing",
                       "rising", "spike", "vibrat", "noise", "leak", "tripping",
                       "is high", "too high", "too hot", "smoke", "burning",
                       "pressure drop", "won't start", "wont start", "breakdown")
_EQUIPMENT_KEYWORDS = ("operating temperature", "normal range", "which bearing", "rated",
                       "specification", "spec", "model number", "manufacturer",
                       "rpm range", "capacity", "part number", "operating range")
_GENERAL_KEYWORDS = ("lockout", "tagout", "safety", "procedure", "sop", "policy",
                     "preventive maintenance", "how do i", "how to", "guideline")
# Interrogative openers that signal a factual (equipment) question, not a symptom.
_SPEC_QUESTION_OPENERS = ("what is", "what's", "whats", "what are", "which", "how much",
                          "how many", "when should", "where is")
_SYMPTOM_KEYWORDS = ("vibration", "temperature", "temp", "pressure", "noise", "current",
                     "rpm", "speed", "overheat", "leak", "smoke", "spark", "trip")


class ConversationAgent:
    """Compiled conversation orchestrator. Construct once and reuse."""

    def __init__(self, db) -> None:
        self._tools = MaintenanceTools(db)
        self._guard = ScopeGuard()
        self._diagnosis = DiagnosisAgent(self._tools)
        self._memory_repo = AgentMemoryRepository(db)
        self._equipment_repo = EquipmentRepository(db)
        self._search = SearchPipeline(
            rag_repository=RagRepository(db),
            equipment_repository=EquipmentRepository(db),
            knowledge_repository=KnowledgeRepository(db),
        )
        self._graph = self._build_graph()

    # -- public API ------------------------------------------------------
    async def chat(
        self,
        *,
        session_id: str,
        equipment_code: str,
        message: str,
        conversation_history: list[dict[str, str]],
        agent_trace_id: str | None = None,
    ) -> ConversationState:
        # Resolve the mandatory equipment once, up front. The equipment *code*
        # is the canonical key used by every tool and persisted health record.
        equipment = await self._equipment_repo.get_by_id(equipment_code)
        initial: ConversationState = {
            "session_id": session_id,
            "message": message,
            "conversation_history": conversation_history or [],
            "equipment_id": equipment_code,
            "equipment_code": equipment_code,
            "equipment_type": equipment.equipment_type if equipment else None,
            "equipment_name": equipment.equipment_name if equipment else None,
            "agent_trace_id": agent_trace_id or str(uuid.uuid4()),
        }
        return await self._graph.ainvoke(initial)

    # -- graph wiring (_04_Agent.md §21) ---------------------------------
    def _build_graph(self):
        g = StateGraph(ConversationState)
        g.add_node("scope_guard", self._scope_guard)
        g.add_node("context_builder", self._context_builder)
        g.add_node("intent_detection", self._intent_detection)
        g.add_node("agent_router", self._agent_router)
        g.add_node("general_agent", self._general_agent)
        g.add_node("equipment_agent", self._equipment_agent)
        g.add_node("diagnosis_agent", self._diagnosis_agent)
        g.add_node("memory_writer", self._memory_writer)
        g.add_node("response_generator", self._response_generator)

        # The content-scope guardrail runs first: off-topic messages skip the
        # whole pipeline and go straight to the response generator with a refusal.
        g.add_edge(START, "scope_guard")
        g.add_conditional_edges(
            "scope_guard", self._after_guard,
            {"continue": "context_builder", "blocked": "response_generator"},
        )
        g.add_edge("context_builder", "intent_detection")
        g.add_edge("intent_detection", "agent_router")
        g.add_conditional_edges(
            "agent_router", self._pick_agent,
            {"general": "general_agent", "equipment": "equipment_agent",
             "diagnosis": "diagnosis_agent"},
        )
        g.add_edge("general_agent", "memory_writer")
        g.add_edge("equipment_agent", "memory_writer")
        g.add_edge("diagnosis_agent", "memory_writer")
        g.add_edge("memory_writer", "response_generator")
        g.add_edge("response_generator", END)
        return g.compile()

    # -- 0. content-scope guardrail --------------------------------------
    async def _scope_guard(self, state: ConversationState) -> dict[str, Any]:
        """Block messages outside the steel-plant maintenance domain.

        Acts as content-filtering middleware at the entry of the workflow: if the
        message is off-topic we set a refusal response and flag the turn blocked
        so it routes straight to the response generator, never touching the
        retrieval / diagnosis agents or external tools.
        """
        in_scope = await self._guard.is_in_scope(
            state.get("message", ""),
            equipment_name=state.get("equipment_name"),
            equipment_type=state.get("equipment_type"),
        )
        if in_scope:
            return {"blocked": False}
        logger.info(
            "Scope guardrail blocked off-topic message (session=%s, trace=%s)",
            state.get("session_id"), state.get("agent_trace_id"),
        )
        return {"blocked": True, "response": REFUSAL_MESSAGE, "citations": []}

    def _after_guard(self, state: ConversationState) -> str:
        return "blocked" if state.get("blocked") else "continue"

    # -- 1. context builder (_04_Agent.md §4) ----------------------------
    async def _context_builder(self, state: ConversationState) -> dict[str, Any]:
        history = [
            {"role": str(t.get("role", "")), "content": str(t.get("content", ""))}
            for t in state.get("conversation_history", [])
            if isinstance(t, dict)
        ]
        message = state.get("message", "").strip()
        normalized = message.lower().strip(" .!?")
        is_affirmation = (
            normalized in _AFFIRMATIONS
            or normalized.startswith(("yes", "yeah", "correct", "that's right", "thats right"))
        )
        return {"conversation_history": history, "is_affirmation": is_affirmation}

    # -- 2. intent detection (_04_Agent.md §5) ---------------------------
    async def _intent_detection(self, state: ConversationState) -> dict[str, Any]:
        message = state.get("message", "")
        # If the previous assistant turn was a co-occurring-symptom probe, this
        # turn is the engineer's answer to it and must continue the diagnosis.
        # Intent detection otherwise only sees the bare message (no history), so a
        # reply like "yes" would misroute to the general agent.
        if self._awaiting_symptom_confirmation(state.get("conversation_history", [])):
            return {"intent": INTENT_DIAGNOSIS, "intent_confidence": 0.9}
        result = await llm_client.complete_json(
            "You classify a maintenance engineer's message into exactly one intent.",
            f"Intents: {sorted(_INTENTS)}\n"
            "- GENERAL_PLANT_QUESTION: plant-wide policy/safety/SOP questions.\n"
            "- EQUIPMENT_QUESTION: facts about a specific equipment (specs, ranges).\n"
            "- DIAGNOSIS_REQUEST: symptoms/failures needing root-cause analysis.\n"
            "- UNKNOWN: anything else.\n"
            f"Message: {message}\n"
            'Return JSON only: {"intent":"...","confidence":0.0}',
            max_tokens=60,
        )
        if result:
            intent = str(result.get("intent", "")).strip().upper().replace(" ", "_")
            if intent in _INTENTS:
                try:
                    conf = float(result.get("confidence", 0.7))
                except (ValueError, TypeError):
                    conf = 0.7
                return {"intent": intent, "intent_confidence": max(0.0, min(1.0, conf))}
        intent, conf = self._heuristic_intent(message, state)
        return {"intent": intent, "intent_confidence": conf}

    def _heuristic_intent(self, message: str, state: ConversationState) -> tuple[str, float]:
        lowered = message.lower()
        # An affirmation continues the prior intent (e.g. confirming equipment).
        if state.get("is_affirmation"):
            prior = self._last_intent_hint(state)
            if prior:
                return prior, 0.6
        scores = {
            INTENT_DIAGNOSIS: sum(1 for k in _DIAGNOSIS_KEYWORDS if k in lowered),
            INTENT_EQUIPMENT: sum(1 for k in _EQUIPMENT_KEYWORDS if k in lowered),
            INTENT_GENERAL: sum(1 for k in _GENERAL_KEYWORDS if k in lowered),
        }
        # A factual interrogative ("what is its operating temperature?") is an
        # equipment question, even though it names a metric -- unless it also
        # describes a symptom (then the diagnosis signal already dominates).
        if (lowered.lstrip().startswith(_SPEC_QUESTION_OPENERS)
                and "how do" not in lowered and "how to" not in lowered):
            scores[INTENT_EQUIPMENT] += 2
        best = max(scores, key=lambda k: scores[k])
        if scores[best] == 0:
            return INTENT_GENERAL, 0.4
        return best, min(0.9, 0.5 + 0.1 * scores[best])

    @staticmethod
    def _last_intent_hint(state: ConversationState) -> str | None:
        for turn in reversed(state.get("conversation_history", [])):
            if turn.get("role") == "assistant" and "confirm" in turn.get("content", "").lower():
                return INTENT_DIAGNOSIS
        return None

    # -- agent router (_04_Agent.md §8) ----------------------------------
    async def _agent_router(self, state: ConversationState) -> dict[str, Any]:
        intent = state.get("intent", INTENT_UNKNOWN)
        route = {
            INTENT_DIAGNOSIS: "diagnosis",
            INTENT_EQUIPMENT: "equipment",
            INTENT_GENERAL: "general",
            INTENT_UNKNOWN: "general",
        }.get(intent, "general")
        return {"route": route}

    def _pick_agent(self, state: ConversationState) -> str:
        return state.get("route", "general")

    # -- live equipment grounding (reuses the prediction-agent tools) ----
    async def _equipment_context(self, state: ConversationState) -> str | None:
        """Assemble a compact markdown snapshot of the equipment's live state.

        Reuses the operational tools added for the prediction agent (health,
        sensor status, anomaly alerts, fault messages, spare-parts inventory) so
        the Q&A agents can answer condition / spares / alert questions with live
        data, not just indexed documents.
        """
        eid = state.get("equipment_id")
        if not eid:
            return None
        parts: list[str] = []
        health = await self._tools.equipment_health(eid)
        if health:
            parts.append(
                f"Current health: score {health.get('health_score')}, risk "
                f"{health.get('risk_level')}, RUL {health.get('rul_days')}d; "
                f"predicted failure: {health.get('predicted_failure')}"
            )
        breaches = (await self._tools.sensor_history(eid)).get("breaches", [])
        if breaches:
            parts.append("Sensor breaches (7d): " + "; ".join(
                f"{b['sensor_code']} {b['status']} (latest {b['latest']})" for b in breaches[:6]))
        anomalies = (await self._tools.get_anomaly_alert(eid, number_of_records=5, hours=24 * 7)).get("rows", [])
        if anomalies:
            parts.append("Recent anomaly alerts (7d): " + "; ".join(
                f"{a.get('sensor_name')} {a.get('alert_level')} dev {a.get('deviation_pct')}%"
                for a in anomalies[:5]))
        faults = (await self._tools.get_fault_error_messages(eid, hours=24 * 7, number_of_records=5)).get("rows", [])
        if faults:
            parts.append("Recent fault/alarm messages (7d): " + "; ".join(
                f"{f.get('fault_code')} [{f.get('message_type')}]: {f.get('message_text')}"
                for f in faults[:5]))
        spares = (await self._tools.get_spare_parts(eid, number_of_records=8)).get("rows", [])
        if spares:
            parts.append("Spare parts: " + "; ".join(
                f"{s.get('part_name')} ({s.get('stock_status')}, stock {s.get('current_stock')}, "
                f"lead {s.get('procurement_lead_time_days')}d)" for s in spares[:8]))
        return "\n".join(parts) if parts else None

    # -- Agent 1: General Knowledge (_04_Agent.md §9) --------------------
    async def _general_agent(self, state: ConversationState) -> dict[str, Any]:
        extra = await self._equipment_context(state)
        result = await self._search.answer(state.get("message", ""), extra_context=extra)
        return {
            "response": result.answer,
            "citations": [{"document": c.document, "page": c.page} for c in result.citations],
        }

    # -- Agent 2: Equipment Knowledge (_04_Agent.md §10) -----------------
    async def _equipment_agent(self, state: ConversationState) -> dict[str, Any]:
        extra = await self._equipment_context(state)
        result = await self._search.answer(
            state.get("message", ""),
            equipment_id=state.get("equipment_id"),
            intent_override="GENERAL_QA",
            extra_context=extra,
        )
        return {
            "response": result.answer,
            "citations": [{"document": c.document, "page": c.page} for c in result.citations],
        }

    # -- Agent 3: Diagnosis (_04_Agent.md §11-12, Enhancement) -----------
    async def _diagnosis_agent(self, state: ConversationState) -> dict[str, Any]:
        # When the turn is just a confirmation ("yes"), the symptoms live in the
        # prior user turn — reuse it as the effective diagnosis question (§4, §15).
        question = self._effective_question(state)
        history = state.get("conversation_history", [])
        symptoms = await self._extract_symptoms(question, history)

        # Engineers under-report symptoms (short-lived or older observations they
        # forget). Before diagnosing, ask once whether they have also seen any
        # symptoms that historically co-occur on this equipment.
        if self._awaiting_symptom_confirmation(history):
            # This turn is the engineer's answer to a prior probe: fold in the
            # confirmed extras and continue to the diagnosis below.
            extras = await self._confirmed_extra_symptoms(state, history)
            symptoms = self._dedupe(symptoms + extras)
        elif not self._already_probed(history):
            # Probe at most once per conversation (for now): only when no earlier
            # turn already asked about co-occurring symptoms.
            candidates = await self._cooccurring_symptoms(
                state.get("equipment_id"), symptoms
            )
            if candidates:
                return {
                    "response": self._format_symptom_probe(candidates, state),
                    "citations": [],
                    "awaiting_symptom_confirmation": True,
                }
            # No historical candidates — diagnose straight away (unchanged path).

        result = await self._diagnosis.run(
            equipment_id=state.get("equipment_id"),
            equipment_code=state.get("equipment_code"),
            equipment_type=state.get("equipment_type"),
            equipment_name=state.get("equipment_name"),
            symptoms=symptoms,
            question=question,
        )
        response = self._format_diagnosis(result, state)
        return {
            "response": response,
            "citations": result.get("citations", []),
            "diagnosis": {
                "diagnosis": result.get("diagnosis"),
                "confidence": result.get("confidence"),
                "symptoms": symptoms or [state.get("message", "")],
            },
        }

    def _effective_question(self, state: ConversationState) -> str:
        message = state.get("message", "")
        if not state.get("is_affirmation"):
            return message
        for turn in reversed(state.get("conversation_history", [])):
            content = turn.get("content", "").strip()
            normalized = content.lower().strip(" .!?")
            if turn.get("role") == "user" and content and normalized not in _AFFIRMATIONS:
                return content
        return message

    async def _extract_symptoms(
        self, question: str, history: list[dict[str, str]] | None = None
    ) -> list[str]:
        """Extract concrete fault symptoms with an LLM, drawing on the current
        question *and* earlier user turns.

        Engineers often state symptoms in an earlier turn ("bearing is
        vibrating") before a later one that just refines or confirms the request
        ("yes, diagnose it"), so we feed the prior user messages as context and
        ask the model to surface every distinct symptom it can find. Falls back
        to the keyword heuristic when OpenAI is unavailable or returns nothing.
        """
        prior_user_messages = [
            str(t.get("content", "")).strip()
            for t in (history or [])
            if isinstance(t, dict) and t.get("role") == "user"
            and str(t.get("content", "")).strip()
        ]
        try:
            result = await llm_client.complete_json(
                "You extract equipment fault symptoms from a maintenance "
                "engineer's conversation. A symptom is an observable abnormal "
                "condition (e.g. 'high vibration', 'bearing temperature rising', "
                "'oil leak', 'tripping on overload'). Ignore greetings, spec "
                "questions and bare confirmations.",
                "List every distinct symptom mentioned, drawing on both the "
                "current message and the earlier user messages. Normalise each "
                "to a short phrase.\n"
                f"Earlier user messages: {prior_user_messages or 'none'}\n"
                f"Current message: {question}\n"
                'Return JSON only: {"symptoms": ["...", "..."]}. '
                "Use an empty list if there are no symptoms.",
                max_tokens=200,
            )
            raw = result.get("symptoms", []) if isinstance(result, dict) else []
            symptoms = self._dedupe([str(s).strip() for s in raw if str(s).strip()])
            if symptoms:
                return symptoms
        except OpenAIUnavailableError:
            logger.warning("LLM symptom extraction unavailable; using heuristic fallback.")
        # Heuristic fallback: scan the prior user turns and the current question.
        fallback: list[str] = []
        for text in [*prior_user_messages, question]:
            fallback.extend(self._extract_symptoms_heuristic(text))
        return self._dedupe(fallback)

    @staticmethod
    def _extract_symptoms_heuristic(message: str) -> list[str]:
        clauses = re.split(r"[,;]|\band\b", message.lower())
        return [
            c.strip() for c in clauses
            if c.strip() and any(k in c for k in _SYMPTOM_KEYWORDS)
        ]

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        """De-duplicate case-insensitively while preserving first-seen order."""
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    # -- co-occurring-symptom probe --------------------------------------
    @staticmethod
    def _latest_assistant(history: list[dict[str, str]]) -> str | None:
        for turn in reversed(history or []):
            if turn.get("role") == "assistant":
                return turn.get("content", "")
        return None

    def _awaiting_symptom_confirmation(self, history: list[dict[str, str]]) -> bool:
        """True when the most recent assistant turn was a symptom probe.

        Looking only at the *latest* assistant message both detects the answer
        turn and prevents re-probing (the turn after a probe always proceeds to
        diagnosis), so the protocol can never loop.
        """
        latest = self._latest_assistant(history)
        return bool(latest and _SYMPTOM_PROBE_MARKER in latest.lower())

    @staticmethod
    def _already_probed(history: list[dict[str, str]]) -> bool:
        """True if *any* earlier assistant turn already issued a symptom probe.

        Used to cap probing at one per conversation: once we've asked about
        co-occurring symptoms, later diagnosis turns go straight to diagnosis.
        """
        return any(
            t.get("role") == "assistant"
            and _SYMPTOM_PROBE_MARKER in t.get("content", "").lower()
            for t in (history or [])
        )

    async def _cooccurring_symptoms(
        self, equipment_id: str | None, reported: list[str]
    ) -> list[str]:
        """Symptoms that historically co-occur with the reported ones and that the
        engineer hasn't already mentioned.

        Retrieves past-incident symptom *sets* for this equipment — each set being
        symptoms that were observed together in one incident — and passes those
        groups to the LLM so it can judge which symptoms tend to accompany the
        reported ones. The grouping is the whole point: a symptom is only a useful
        suggestion because it appeared *alongside* something the engineer is
        seeing now. Falls back to a deterministic co-occurrence count over the same
        groups when OpenAI is unavailable or returns nothing.
        """
        groups = await self._tools.historical_symptom_groups(equipment_id)
        if not groups:
            return []
        # Universe of suggestable symptoms = everything that appears in a group,
        # excluding what the engineer already reported.
        pool = {
            s.lower(): s
            for g in groups for s in g
            if not self._already_reported(s, reported)
        }
        if not pool:
            return []
        reported_text = ", ".join(reported) if reported else "none stated yet"
        groups_text = "\n".join(f"- {g}" for g in groups[:20])
        try:
            result = await llm_client.complete_json(
                "You help a maintenance engineer recall symptoms they may have "
                "forgotten. You are given the symptoms they already reported and a "
                "list of symptom SETS, where each set is the symptoms that were "
                "observed together in one past incident on this same equipment. "
                "Using which symptoms historically co-occur with the reported ones, "
                "pick the symptoms most worth asking the engineer about. Choose "
                "only symptoms that appear in the sets; do not invent new ones and "
                "do not repeat the reported symptoms.",
                f"Reported symptoms: {reported_text}\n"
                f"Past-incident symptom sets (each line = symptoms seen together):\n"
                f"{groups_text}\n"
                f"Return at most {_MAX_PROBE_SYMPTOMS}, most relevant first.\n"
                'Return JSON only: {"symptoms": ["...", "..."]}.',
                max_tokens=250,
            )
            raw = result.get("symptoms", []) if isinstance(result, dict) else []
            # Keep only model picks that genuinely appear in the grouped pool.
            picked = self._dedupe(
                [pool[str(s).strip().lower()] for s in raw
                 if str(s).strip().lower() in pool]
            )
            if picked:
                return picked[:_MAX_PROBE_SYMPTOMS]
        except OpenAIUnavailableError:
            logger.warning("LLM co-occurring-symptom selection unavailable; using fallback.")
        return self._cooccurring_fallback(groups, reported)

    def _cooccurring_fallback(
        self, groups: list[list[str]], reported: list[str]
    ) -> list[str]:
        """Deterministic grouping-based co-occurrence (LLM-unavailable safety net).

        Prefers symptoms drawn from incidents that share one of the reported
        symptoms (true co-occurrence). If none overlap — common, since reported
        phrasing rarely matches the verbose recorded text — falls back to the
        symptoms that appear across the most incident groups, which are the most
        broadly associated and so the most worth asking about.
        """
        from collections import Counter

        overlap: list[str] = []
        for g in groups:
            if any(self._already_reported(s, reported) for s in g):
                overlap += [s for s in g if not self._already_reported(s, reported)]
        deduped = self._dedupe(overlap)
        if deduped:
            return deduped[:_MAX_PROBE_SYMPTOMS]

        counts: Counter[str] = Counter()
        for g in groups:
            for s in g:
                if not self._already_reported(s, reported):
                    counts[s] += 1
        return [s for s, _ in counts.most_common(_MAX_PROBE_SYMPTOMS)]

    @staticmethod
    def _already_reported(candidate: str, reported: list[str]) -> bool:
        """Case-insensitive overlap test between a candidate and reported symptoms."""
        cand = candidate.lower().strip()
        for r in reported:
            rl = r.lower().strip()
            if cand and rl and (cand in rl or rl in cand):
                return True
        return False

    def _format_symptom_probe(
        self, candidates: list[str], state: ConversationState
    ) -> str:
        label = state.get("equipment_code") or state.get("equipment_id") or "this equipment"
        lines = [
            f"Before I diagnose, {_SYMPTOM_PROBE_MARKER} on {label} "
            "(they often occur together with what you've described)?",
            "",
        ]
        lines += [f"- {c}" for c in candidates]
        lines += ["", "Reply with any that apply, or 'no' if none."]
        return "\n".join(lines)

    @staticmethod
    def _parse_probe_candidates(probe_text: str) -> list[str]:
        """Recover the bulleted candidate symptoms from a prior probe message."""
        out: list[str] = []
        for line in (probe_text or "").splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                item = stripped[2:].strip()
                if item:
                    out.append(item)
        return out

    async def _confirmed_extra_symptoms(
        self, state: ConversationState, history: list[dict[str, str]]
    ) -> list[str]:
        """Which probed candidates the engineer just confirmed (plus any new ones).

        Parses the candidate list back out of the prior probe message, then uses
        the LLM to decide which the engineer's reply confirms and to capture any
        brand-new symptom they add. Heuristic fallback covers bare affirmations
        ("yes" -> all), negations ("no" -> none), and substring mentions.
        """
        probe = self._latest_assistant(history) or ""
        candidates = self._parse_probe_candidates(probe)
        message = state.get("message", "")
        try:
            result = await llm_client.complete_json(
                "A maintenance engineer was asked whether they had also observed "
                "any of a list of candidate symptoms. From their reply, return the "
                "candidates they confirmed observing, plus any additional symptom "
                "they mention that is not in the list. If they decline (e.g. 'no'), "
                "return an empty list.",
                f"Candidate symptoms asked about: {candidates}\n"
                f"Engineer reply: {message}\n"
                'Return JSON only: {"symptoms": ["...", "..."]}.',
                max_tokens=200,
            )
            raw = result.get("symptoms", []) if isinstance(result, dict) else []
            confirmed = self._dedupe([str(s).strip() for s in raw if str(s).strip()])
            if confirmed:
                return confirmed
            # An explicit empty list is a valid "none" answer — trust it.
            if isinstance(result, dict) and "symptoms" in result:
                return []
        except OpenAIUnavailableError:
            logger.warning("LLM symptom-confirmation parse unavailable; using heuristic.")
        return self._confirmed_extra_symptoms_heuristic(message, candidates)

    def _confirmed_extra_symptoms_heuristic(
        self, message: str, candidates: list[str]
    ) -> list[str]:
        normalized = message.lower().strip(" .!?")
        if normalized.startswith(_NEGATIONS):
            return []
        if normalized in _AFFIRMATIONS or normalized.startswith(("yes", "yeah", "yep")):
            return list(candidates)
        return [c for c in candidates if c.lower() in message.lower()]

    def _format_diagnosis(self, result: dict[str, Any], state: ConversationState) -> str:
        # Prefer the templated, relevance-filtered report from the diagnosis
        # graph's compose node. Fall back to the structured concatenation only
        # if composition was skipped or the LLM call failed.
        report = result.get("report_markdown")
        if report:
            return report

        diagnosis = result.get("diagnosis", "Undetermined")
        confidence = result.get("confidence", 0.0)
        label = state.get("equipment_code") or state.get("equipment_id") or "the equipment"
        lines = [f"Most likely diagnosis for {label}: **{diagnosis}** "
                 f"(confidence {confidence:.0%})."]

        alts = result.get("alternative_causes", [])
        if alts:
            lines.append("\nAlternative causes considered:")
            lines += [f"  - {a['cause']} ({a['confidence']:.0%})" for a in alts]

        evidence = result.get("evidence_summary", [])
        if evidence:
            lines.append("\nSupporting evidence:")
            lines += [f"  - [{e['type']}] {e['details']}" for e in evidence]

        recs = result.get("recommendations", {})
        for label_text, key in (
            ("Immediate actions", "immediate_actions"),
            ("Recommended inspections", "recommended_inspections"),
            ("Recommended repairs", "recommended_repairs"),
            ("Preventive actions", "preventive_actions"),
        ):
            items = recs.get(key, [])
            if items:
                lines.append(f"\n{label_text}:")
                lines += [f"  - {item}" for item in items]
        return "\n".join(lines)

    # -- memory writer (_04_Agent.md §14-20) -----------------------------
    async def _memory_writer(self, state: ConversationState) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        intent = state.get("intent", INTENT_UNKNOWN)
        diagnosis = state.get("diagnosis")

        if intent == INTENT_DIAGNOSIS and diagnosis and diagnosis.get("diagnosis"):
            # Episodic memory: store the validated diagnosis for memory-assisted
            # hypothesis generation on future requests (§15-16).
            await self._write_memory(
                equipment_id=state.get("equipment_id"),
                interaction_type=InteractionType.DIAGNOSIS.value,
                user_query=", ".join(diagnosis.get("symptoms", [])) or state.get("message", ""),
                agent_response=f"{diagnosis['diagnosis']} ({diagnosis.get('confidence', 0.0)})",
                outcome=Outcome.PENDING.value,
                created_at=now,
            )
        else:
            await self._write_memory(
                equipment_id=state.get("equipment_id"),
                interaction_type=InteractionType.CHAT.value,
                user_query=state.get("message", ""),
                agent_response=(state.get("response", "") or "")[:2000],
                outcome=Outcome.PENDING.value,
                created_at=now,
            )

        # Automatic feedback signal from the conversation flow (§19).
        await self._maybe_write_feedback(state, now)
        return {}

    async def _maybe_write_feedback(self, state: ConversationState, now: datetime) -> None:
        history = state.get("conversation_history", [])
        if not history:
            return
        last_assistant = next(
            (t for t in reversed(history) if t.get("role") == "assistant"), None
        )
        if not last_assistant or "diagnosis" not in last_assistant.get("content", "").lower():
            return
        normalized = state.get("message", "").lower().strip()
        if normalized.startswith(_NEGATIONS):
            outcome = Outcome.DIAGNOSIS_REJECTED.value
        elif state.get("is_affirmation") or "how do i" in normalized or "how to" in normalized:
            outcome = Outcome.DIAGNOSIS_CONFIRMED.value
        else:
            return
        await self._write_memory(
            equipment_id=state.get("equipment_id"),
            interaction_type=InteractionType.FEEDBACK.value,
            user_query=state.get("message", ""),
            agent_response=last_assistant.get("content", "")[:2000],
            outcome=outcome,
            created_at=now,
        )

    async def _write_memory(self, **kwargs: Any) -> None:
        await self._memory_repo.insert(AgentMemory(id=str(uuid.uuid4()), **kwargs))

    # -- response generator (_04_Agent.md §2) ----------------------------
    async def _response_generator(self, state: ConversationState) -> dict[str, Any]:
        return {
            "response": state.get("response") or "I'm sorry, I couldn't produce an answer.",
            "citations": state.get("citations", []),
            "equipment_code": state.get("equipment_code"),
            "agent_trace_id": state.get("agent_trace_id") or str(uuid.uuid4()),
        }


# -- module-level singleton ------------------------------------------------
_conversation_agent: ConversationAgent | None = None


def get_conversation_agent() -> ConversationAgent:
    """Return the shared conversation agent, building (and compiling) it once."""
    global _conversation_agent
    if _conversation_agent is None:
        from database.connection import db

        _conversation_agent = ConversationAgent(db)
    return _conversation_agent
