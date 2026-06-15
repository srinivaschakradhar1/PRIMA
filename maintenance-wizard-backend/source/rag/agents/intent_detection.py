"""Equipment Detection and Intent Detection agents (search pipeline)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from rag.llm import llm_client

logger = logging.getLogger(__name__)

INTENTS = ["DIAGNOSIS", "ROOT_CAUSE", "PROCEDURE", "MAINTENANCE_PLAN", "SPARE_PART", "GENERAL_QA"]

_CODE_RE = re.compile(r"\b[A-Z]{1,5}-?\d{2,4}\b")


@dataclass
class DetectedEquipment:
    equipment_id: str
    equipment_code: str | None
    equipment_type: str | None


class EquipmentDetectionAgent:
    """Resolves a question to a known equipment record via code/name matching."""

    def run(self, question: str, known_equipment: list) -> DetectedEquipment | None:
        q_upper = question.upper()
        # 1. Exact equipment-code match.
        for eq in known_equipment:
            code = (eq.equipment_code or "").upper()
            if code and code in q_upper:
                return DetectedEquipment(eq.id, eq.equipment_code, eq.equipment_type)
        # 2. Loose code pattern -> match against known codes ignoring separators.
        candidates = {c.replace("-", "") for c in _CODE_RE.findall(q_upper)}
        if candidates:
            for eq in known_equipment:
                norm = (eq.equipment_code or "").upper().replace("-", "")
                if norm and norm in candidates:
                    return DetectedEquipment(eq.id, eq.equipment_code, eq.equipment_type)
        # 3. Equipment-name match.
        q_lower = question.lower()
        for eq in known_equipment:
            name = (eq.equipment_name or "").lower()
            if name and len(name) > 4 and name in q_lower:
                return DetectedEquipment(eq.id, eq.equipment_code, eq.equipment_type)
        return None


class IntentDetectionAgent:
    async def run(self, question: str) -> str:
        result = await llm_client.complete_json(
            "You classify maintenance engineer questions.",
            f"Classify the intent of this question into one of {INTENTS}.\n"
            f"Question: {question}\n"
            'Return JSON only: {"intent": "..."}',
            max_tokens=50,
        )
        intent = str(result.get("intent", "")).strip().upper().replace(" ", "_")
        return intent if intent in INTENTS else "GENERAL_QA"
