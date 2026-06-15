"""Content-scope guardrail for the conversation agent.

The maintenance wizard is a *steel-plant* assistant: it answers questions about
plant equipment, maintenance, diagnostics, safety / SOPs, sensors, spare parts
and steel operations, and it must politely refuse anything outside that domain
(general trivia, coding help, medical/legal advice, current events, etc.).

This filter runs as the **first node of the conversation graph** so off-topic
requests are short-circuited before they reach the retrieval / diagnosis agents.
That keeps answers grounded, avoids spending tokens (and tool calls) on requests
the assistant should not serve, and gives the user a consistent refusal message.

Classification is LLM-driven (consistent with intent detection) with a keyword
heuristic fallback so the guardrail still functions when OpenAI is unavailable.
The heuristic *fails open* on genuinely ambiguous input — a steel-plant question
phrased unusually should get through; only clearly off-topic input is blocked.
"""

from __future__ import annotations

import logging

from rag.llm import llm_client

logger = logging.getLogger(__name__)

# Returned verbatim to the user when a message is judged out of scope.
REFUSAL_MESSAGE = (
    "I'm the steel-plant maintenance assistant, so I can only help with questions "
    "about the plant — its equipment, maintenance, diagnostics, sensors, spare "
    "parts, safety procedures and operations. That request falls outside what I "
    "can help with. Please ask me something about the plant or its equipment."
)

# Short replies that simply continue an in-scope conversation (confirmations,
# acknowledgements). These are never blocked on their own.
_FOLLOW_UP_TERMS = {
    "yes", "yeah", "yep", "no", "nope", "ok", "okay", "sure", "correct",
    "right", "confirm", "confirmed", "thanks", "thank you", "got it", "please",
    "continue", "go on", "more", "why", "how", "and", "what about",
}

# Strong on-topic signals: plant equipment, conditions, maintenance vocabulary
# and steel-making domain terms. Any hit means "allow".
_ON_TOPIC_KEYWORDS = (
    "equipment", "machine", "maintenance", "maintain", "repair", "service",
    "diagnos", "fault", "failure", "breakdown", "downtime", "inspect",
    "lubricat", "overhaul", "spare", "part", "inventory", "stock",
    "sensor", "reading", "vibration", "temperature", "pressure", "current",
    "rpm", "speed", "noise", "leak", "overheat", "anomaly", "alarm", "alert",
    "health", "rul", "remaining useful life", "predict", "risk",
    "bearing", "motor", "pump", "gearbox", "compressor", "conveyor", "valve",
    "hydraulic", "pneumatic", "lubrication", "coolant", "shaft", "rotor",
    "furnace", "blast furnace", "rolling mill", "caster", "ladle", "tundish",
    "slag", "molten", "ingot", "billet", "coke", "sinter", "annealing",
    "rolling", "casting", "smelt", "crane", "kiln",
    "plant", "steel", "mill", "production line", "shift", "operator",
    "safety", "lockout", "tagout", "sop", "procedure", "policy", "guideline",
    "preventive", "predictive", "condition monitoring",
)

# Clearly off-topic domains. Used only when no on-topic signal is present.
_OFF_TOPIC_KEYWORDS = (
    "recipe", "cook", "movie", "film", "song", "lyrics", "celebrity", "actor",
    "football", "cricket", "basketball", "sport", "weather", "horoscope",
    "stock price", "crypto", "bitcoin", "election", "president", "politic",
    "poem", "joke", "story", "dating", "girlfriend", "boyfriend",
    "homework", "essay", "translate", "write code", "python", "javascript",
    "history of", "capital of", "meaning of life", "religion", "medical",
    "diagnose me", "symptom i have", "love", "vacation", "holiday", "travel",
)


class ScopeGuard:
    """Decides whether a user message is within the steel-plant assistant's scope."""

    async def is_in_scope(
        self,
        message: str,
        *,
        equipment_name: str | None = None,
        equipment_type: str | None = None,
    ) -> bool:
        """Return ``True`` if the message should be answered, ``False`` to refuse.

        Tries the LLM classifier first; on any failure (e.g. OpenAI unavailable)
        falls back to the keyword heuristic so the guardrail never crashes the
        request pipeline.
        """
        text = (message or "").strip()
        if not text:
            # Nothing to answer; let the downstream flow handle the empty turn.
            return True

        # Trivial follow-ups / confirmations are always allowed — they only make
        # sense as a continuation of an already in-scope conversation.
        normalized = text.lower().strip(" .!?")
        if normalized in _FOLLOW_UP_TERMS or len(normalized.split()) <= 2:
            return True

        try:
            decision = await self._classify_with_llm(text, equipment_name, equipment_type)
            if decision is not None:
                return decision
        except Exception:  # pragma: no cover - defensive; never break the turn
            logger.warning("Scope guardrail LLM check failed; using heuristic", exc_info=True)

        return self._heuristic_in_scope(normalized)

    async def _classify_with_llm(
        self, message: str, equipment_name: str | None, equipment_type: str | None
    ) -> bool | None:
        context = ""
        if equipment_name or equipment_type:
            context = (
                f"The engineer is currently working on equipment "
                f"'{equipment_name or ''}' (type: {equipment_type or 'unknown'}).\n"
            )
        result = await llm_client.complete_json(
            "You are a content filter for a STEEL PLANT maintenance assistant. "
            "Decide whether a message is within scope. In scope: anything about "
            "the steel plant, its equipment, maintenance, repairs, diagnostics, "
            "sensors, spare parts, safety/SOPs, operations, or steel-making "
            "processes. Out of scope: general knowledge, trivia, coding help, "
            "medical/legal/financial advice, current events, entertainment, or "
            "any topic unrelated to running and maintaining a steel plant.",
            f"{context}Message: {message}\n"
            'Return JSON only: {"in_scope": true|false, "reason": "..."}',
            max_tokens=80,
        )
        if not result or "in_scope" not in result:
            return None
        return bool(result.get("in_scope"))

    @staticmethod
    def _heuristic_in_scope(normalized: str) -> bool:
        """Keyword fallback. Allow on any on-topic signal; otherwise block only
        clearly off-topic input and *fail open* on ambiguity."""
        if any(kw in normalized for kw in _ON_TOPIC_KEYWORDS):
            return True
        if any(kw in normalized for kw in _OFF_TOPIC_KEYWORDS):
            return False
        return True
