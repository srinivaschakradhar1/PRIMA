"""Concept Extraction Agent (+ section-type classification).

For each merged concept section, determine:
  * concept name
  * concept type / section type (one of the supported taxonomy values)
  * semantic groups present (Symptoms, Root Causes, Corrective Actions, ...)

Mutates the :class:`MergedSection` in place. Requires OpenAI; raises
:class:`~rag.errors.OpenAIUnavailableError` when it is unavailable (no offline
keyword fallback).
"""

from __future__ import annotations

import logging

from rag.llm import llm_client
from rag.models import MergedSection

logger = logging.getLogger(__name__)

SECTION_TYPES = [
    "GENERAL_DESCRIPTION", "FAILURE_MODE", "SOP", "MAINTENANCE_TASK",
    "INSPECTION", "SAFETY", "SPARE_PART", "TROUBLESHOOTING",
    "SENSOR_SPECIFICATION", "OTHER",
]

_SYSTEM = "You are an industrial maintenance knowledge engineer."

_PROMPT = """Analyse this maintenance concept section and classify it.

Heading / concept: {concept}
Text (excerpt):
{text}

Return JSON only with this exact shape:
{{
  "concept": "short concept name",
  "concept_type": one of {types},
  "section_type": one of {types},
  "groups": ["Symptoms", "Root Causes", ...]
}}"""


def _normalise_type(value: str | None) -> str:
    if not value:
        return "OTHER"
    candidate = value.strip().upper().replace(" ", "_").replace("-", "_")
    return candidate if candidate in SECTION_TYPES else "OTHER"


class ConceptExtractionAgent:
    async def run(self, section: MergedSection) -> MergedSection:
        result = await llm_client.complete_json(
            _SYSTEM,
            _PROMPT.format(
                concept=section.concept_name,
                text=_excerpt(section.text),
                types=", ".join(SECTION_TYPES),
            ),
            max_tokens=400,
        )
        section.concept_name = (result.get("concept") or section.concept_name).strip()
        section.concept_type = _normalise_type(result.get("concept_type"))
        section.section_type = _normalise_type(result.get("section_type"))
        groups = result.get("groups") or []
        if isinstance(groups, list):
            section.semantic_groups = [str(g).strip() for g in groups if str(g).strip()]
        return section


def _excerpt(text: str, limit: int = 1600) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + " ..."
