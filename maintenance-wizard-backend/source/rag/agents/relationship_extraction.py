"""Relationship Extraction Agent.

Builds a maintenance knowledge graph as (source, relation, target) triples via
GPT. Requires OpenAI; raises :class:`~rag.errors.OpenAIUnavailableError` when it
is unavailable (no offline fallback).
"""

from __future__ import annotations

import logging

from rag.llm import llm_client
from rag.models import MergedSection, Relationship

logger = logging.getLogger(__name__)

SUPPORTED_RELATIONS = [
    "HAS_SYMPTOM", "HAS_CAUSE", "CORRECTED_BY", "PREVENTED_BY", "REQUIRES_PART",
    "AFFECTS_EQUIPMENT", "FOLLOWS_PROCEDURE", "INDICATES_FAILURE",
    "RESOLVES_ISSUE", "RELATED_TO",
]

_SYSTEM = "You are an industrial maintenance knowledge engineer."

_PROMPT = """Extract maintenance knowledge relationships from this concept as \
triples. Use only these relation types: {relations}.

Concept: {concept}
Text (excerpt):
{text}

Return JSON only:
{{"relationships": [{{"source": "...", "relation": "HAS_SYMPTOM", "target": "..."}}]}}"""


def _normalise_relation(value: str | None) -> str:
    if not value:
        return "RELATED_TO"
    candidate = value.strip().upper().replace(" ", "_").replace("-", "_")
    return candidate if candidate in SUPPORTED_RELATIONS else "RELATED_TO"


class RelationshipExtractionAgent:
    async def run(
        self, section: MergedSection, document_id: str, equipment_id: str | None
    ) -> list[Relationship]:
        result = await llm_client.complete_json(
            _SYSTEM,
            _PROMPT.format(
                relations=", ".join(SUPPORTED_RELATIONS),
                concept=section.concept_name,
                text=_excerpt(section.text),
            ),
            max_tokens=700,
        )
        triples = result.get("relationships") or []
        out: list[Relationship] = []
        for triple in triples:
            if not isinstance(triple, dict):
                continue
            source = str(triple.get("source", "")).strip() or section.concept_name
            target = str(triple.get("target", "")).strip()
            if not target:
                continue
            out.append(
                Relationship(
                    document_id=document_id,
                    equipment_id=equipment_id,
                    source=source,
                    relation=_normalise_relation(triple.get("relation")),
                    target=target,
                    concept=section.concept_name,
                )
            )
        return out


def _excerpt(text: str, limit: int = 1600) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + " ..."
