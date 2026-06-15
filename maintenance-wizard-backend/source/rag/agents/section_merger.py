"""Semantic Section Merger Agent.

Merges adjacent structural sections that describe the same maintenance concept
(e.g. "Bearing Failure Symptoms" + "Bearing Failure Causes" -> "Bearing
Failure"). Structural rules resolve most merges for free; only genuine siblings
are sent to GPT (cost optimisation, design §9-10), with the *next* section
included as context to improve accuracy (§11). Requires OpenAI for the sibling
case; raises :class:`~rag.errors.OpenAIUnavailableError` when it is unavailable.
"""

from __future__ import annotations

import logging
import uuid

import numpy as np

from rag.config import SETTINGS
from rag.embeddings import cosine_similarity
from rag.llm import llm_client
from rag.models import DocumentSection, MergedSection

logger = logging.getLogger(__name__)

_SYSTEM = "You are an industrial maintenance knowledge engineer."

_PROMPT_TEMPLATE = """Determine whether these document sections belong to the \
same maintenance concept (e.g. symptoms, causes and corrective actions of one \
failure mode all belong together; an unrelated lubrication schedule does not).

Section A heading: {a_heading}
Section A text (excerpt):
{a_text}

Section B heading: {b_heading}
Section B text (excerpt):
{b_text}

Upcoming Section C heading (context only, do not merge): {c_heading}

Return JSON only:
{{"same_concept": true, "confidence": 0.0, "concept_name": "..."}}"""


# A section shorter than this (and not a table) is a stray fragment — a wrapped
# heading line, a figure caption, a clause number — that should attach to its
# neighbour rather than survive as its own "concept".
_TINY_SECTION_TOKENS = 40


class SemanticSectionMergerAgent:
    def __init__(self) -> None:
        self._threshold = SETTINGS.merge_similarity_threshold
        self._min_conf = SETTINGS.merge_min_confidence

    async def run(
        self,
        full_text: str,
        sections: list[DocumentSection],
        embeddings: np.ndarray,
    ) -> list[MergedSection]:
        if not sections:
            return []

        merged: list[MergedSection] = []
        pending = _to_merged(sections[0], full_text)
        pending_emb = embeddings[0].astype(np.float32).copy()
        pending_count = 1

        for i in range(1, len(sections)):
            cur = sections[i]

            decision = self._structural_decision(pending, cur)
            if decision is True:
                pending = _merge(pending, cur, full_text, pending.concept_name)
                pending_emb = _running_mean(pending_emb, pending_count, embeddings[i])
                pending_count += 1
                continue
            if decision is False:
                merged.append(pending)
                pending, pending_emb, pending_count = _reset(cur, full_text, embeddings[i])
                continue

            # decision is None -> sibling sections; fall back to the semantic gate.
            sim = cosine_similarity(pending_emb, embeddings[i])
            if sim < self._threshold:
                merged.append(pending)
                pending, pending_emb, pending_count = _reset(cur, full_text, embeddings[i])
                continue

            nxt = sections[i + 1] if i + 1 < len(sections) else None
            same, concept_name = await self._compare(pending, cur, nxt)

            if same:
                pending = _merge(pending, cur, full_text, concept_name)
                pending_emb = _running_mean(pending_emb, pending_count, embeddings[i])
                pending_count += 1
            else:
                merged.append(pending)
                pending, pending_emb, pending_count = _reset(cur, full_text, embeddings[i])

        merged.append(pending)
        logger.info("Section merge: %d raw -> %d concept section(s).", len(sections), len(merged))
        return merged

    @staticmethod
    def _structural_decision(pending: MergedSection, cur: DocumentSection) -> bool | None:
        """Resolve a merge from document structure alone, before the cost gate.

        Returns ``True`` to merge, ``False`` to split, or ``None`` to defer to the
        embedding + LLM semantic comparison (the two sections are siblings).
        """
        # Tables are self-contained units: never fuse them into prose (or vice
        # versa), so a dimensional/spare-parts table stays a single chunk.
        if cur.is_table or pending.is_table:
            return False
        # A deeper heading (e.g. clause 6.2.1 under 6.2) belongs to the concept it
        # sits inside — merge by containment without paying for an LLM call.
        if cur.heading_level > pending.heading_level:
            return True
        # Absorb stray fragments so they cannot break adjacency for real sections.
        if cur.token_estimate < _TINY_SECTION_TOKENS:
            return True
        return None

    async def _compare(
        self,
        pending: MergedSection,
        cur: DocumentSection,
        nxt: DocumentSection | None,
    ) -> tuple[bool, str]:
        result = await llm_client.complete_json(
            _SYSTEM,
            _PROMPT_TEMPLATE.format(
                a_heading=pending.concept_name,
                a_text=_excerpt(pending.text),
                b_heading=cur.heading,
                b_text=_excerpt(cur.text),
                c_heading=nxt.heading if nxt else "(none)",
            ),
            max_tokens=200,
        )
        same = bool(result.get("same_concept"))
        confidence = float(result.get("confidence", 0.0) or 0.0)
        name = (result.get("concept_name") or pending.concept_name).strip()
        if same and confidence < self._min_conf:
            same = False
        return same, name


def _excerpt(text: str, limit: int = 900) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + " ..."


def _to_merged(section: DocumentSection, full_text: str) -> MergedSection:
    return MergedSection(
        id=str(uuid.uuid4()),
        concept_name=section.heading,
        section_ids=[section.id],
        page_number=section.page_number,
        start_offset=section.start_offset,
        end_offset=section.end_offset,
        text=full_text[section.start_offset:section.end_offset],
        heading_level=section.heading_level,
        is_table=section.is_table,
    )


def _reset(section: DocumentSection, full_text: str, emb: np.ndarray):
    return _to_merged(section, full_text), emb.astype(np.float32).copy(), 1


def _merge(pending: MergedSection, cur: DocumentSection, full_text: str, concept_name: str) -> MergedSection:
    start = min(pending.start_offset, cur.start_offset)
    end = max(pending.end_offset, cur.end_offset)
    pending.concept_name = concept_name or pending.concept_name
    pending.section_ids.append(cur.id)
    pending.start_offset = start
    pending.end_offset = end
    pending.text = full_text[start:end]  # sliced from source, never generated
    # Keep the most prominent heading level so further containment merges work.
    pending.heading_level = min(pending.heading_level, cur.heading_level)
    pending.is_table = pending.is_table or cur.is_table
    return pending


def _running_mean(mean_vec: np.ndarray, count: int, new_vec: np.ndarray) -> np.ndarray:
    updated = (mean_vec * count + new_vec) / (count + 1)
    norm = float(np.linalg.norm(updated))
    return updated / norm if norm else updated
