"""Chunk Boundary Agent.

Determines parent-chunk and child-chunk boundaries for a merged concept
section and returns :class:`Chunk` objects. Boundaries are computed as
character offsets and the text is always sliced from the source section (never
generated), per design §16 ("Return offsets only").

Parents represent complete maintenance concepts (~1500-2500 tokens); children
represent semantic groups (~200-500 tokens). Boundaries are packed along
paragraph/sentence units so they never cut mid-word, and each child is labelled
with its semantic type.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from rag.config import SETTINGS
from rag.models import Chunk, MergedSection
from rag.tokenization import count_tokens

_PARA_SEP = re.compile(r"\n\s*\n")
_SENTENCE_SEP = re.compile(r"(?<=[.!?])\s+")

_CHILD_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "SYMPTOMS": ("symptom", "indication", "observed", "abnormal", "sign of"),
    "ROOT_CAUSES": ("cause", "reason", "due to", "caused by"),
    "CORRECTIVE_ACTIONS": ("corrective", "repair", "replace", "rectif", "resolution", "remedy"),
    "PREVENTIVE_ACTIONS": ("preventive", "prevent", "periodic", "scheduled"),
    "SPARE_PARTS": ("spare", "part number", "bom", "component"),
    "SAFETY": ("safety", "hazard", "warning", "caution", "lockout"),
    "INSPECTION": ("inspect", "check", "monitor"),
}


def _classify_child(text: str, groups: list[str]) -> str:
    lowered = text.lower()
    best, best_score = "GENERAL", 0
    for stype, keywords in _CHILD_TYPE_KEYWORDS.items():
        score = sum(lowered.count(kw) for kw in keywords)
        if score > best_score:
            best, best_score = stype, score
    if best == "GENERAL" and groups:
        return groups[0].upper().replace(" ", "_")
    return best


def _blocks(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Split ``text[start:end]`` into non-empty paragraph blocks (abs offsets)."""
    blocks: list[tuple[int, int]] = []
    idx = start
    for m in _PARA_SEP.finditer(text, start, end):
        if text[idx:m.start()].strip():
            blocks.append((idx, m.start()))
        idx = m.end()
    if text[idx:end].strip():
        blocks.append((idx, end))
    return blocks or [(start, end)]


def _split_oversized(text: str, start: int, end: int, hard_cap: int) -> list[tuple[int, int]]:
    """Ensure no unit exceeds ``hard_cap`` tokens by sentence/char splitting."""
    if count_tokens(text[start:end]) <= hard_cap:
        return [(start, end)]
    units: list[tuple[int, int]] = []
    idx = start
    for m in _SENTENCE_SEP.finditer(text, start, end):
        if text[idx:m.start()].strip():
            units.append((idx, m.start()))
        idx = m.start() + (m.end() - m.start())
    if text[idx:end].strip():
        units.append((idx, end))
    # Char-window any sentence that is still too large.
    final: list[tuple[int, int]] = []
    approx_chars = hard_cap * 4
    for s, e in units or [(start, end)]:
        if count_tokens(text[s:e]) <= hard_cap:
            final.append((s, e))
            continue
        cur = s
        while cur < e:
            nxt = min(e, cur + approx_chars)
            final.append((cur, nxt))
            cur = nxt
    return final


def _pack(units: list[tuple[int, int]], text: str, max_tokens: int, min_tokens: int) -> list[tuple[int, int]]:
    """Pack contiguous units into windows of <= ``max_tokens`` (merging tiny tails)."""
    windows: list[tuple[int, int]] = []
    win_start: int | None = None
    win_end = 0
    win_tokens = 0
    for s, e in units:
        unit_tokens = count_tokens(text[s:e])
        if win_start is None:
            win_start, win_end, win_tokens = s, e, unit_tokens
            continue
        if win_tokens + unit_tokens > max_tokens and win_tokens >= min_tokens:
            windows.append((win_start, win_end))
            win_start, win_end, win_tokens = s, e, unit_tokens
        else:
            win_end, win_tokens = e, win_tokens + unit_tokens
    if win_start is not None:
        windows.append((win_start, win_end))
    return windows


class ChunkBoundaryAgent:
    def run(
        self,
        section: MergedSection,
        *,
        document_id: str,
        equipment_id: str | None,
        equipment_type: str | None,
        document_type: str | None,
    ) -> list[Chunk]:
        text = section.text
        abs_start = section.start_offset
        n = len(text)
        now = datetime.now(timezone.utc)

        # 1. Parent boundaries (split only if the concept is very large).
        para_blocks = _blocks(text, 0, n)
        if count_tokens(text) > SETTINGS.parent_max_tokens * 1.4:
            parent_units: list[tuple[int, int]] = []
            for s, e in para_blocks:
                parent_units.extend(_split_oversized(text, s, e, SETTINGS.parent_max_tokens))
            parent_windows = _pack(
                parent_units, text, SETTINGS.parent_max_tokens, SETTINGS.parent_min_tokens
            )
        else:
            parent_windows = [(0, n)]

        chunks: list[Chunk] = []
        for p_start, p_end in parent_windows:
            parent_id = str(uuid.uuid4())
            chunks.append(
                Chunk(
                    chunk_id=parent_id,
                    document_id=document_id,
                    equipment_id=equipment_id,
                    equipment_type=equipment_type,
                    document_type=document_type,
                    concept=section.concept_name,
                    semantic_type=section.section_type or "OTHER",
                    page=section.page_number,
                    start_offset=abs_start + p_start,
                    end_offset=abs_start + p_end,
                    text=text[p_start:p_end],
                    is_parent=True,
                    parent_chunk_id=None,
                    token_count=count_tokens(text[p_start:p_end]),
                    is_table=section.is_table,
                    created_at=now,
                )
            )

            # 2. Child boundaries within this parent. A table is kept intact as a
            #    single child so its rows are never split across chunks.
            if section.is_table:
                child_windows = [(p_start, p_end)]
            else:
                child_units: list[tuple[int, int]] = []
                for s, e in _blocks(text, p_start, p_end):
                    child_units.extend(_split_oversized(text, s, e, SETTINGS.child_max_tokens))
                child_windows = _pack(
                    child_units, text, SETTINGS.child_max_tokens, SETTINGS.child_min_tokens
                )
            for c_start, c_end in child_windows:
                child_text = text[c_start:c_end]
                if not child_text.strip():
                    continue
                chunks.append(
                    Chunk(
                        chunk_id=str(uuid.uuid4()),
                        document_id=document_id,
                        equipment_id=equipment_id,
                        equipment_type=equipment_type,
                        document_type=document_type,
                        concept=section.concept_name,
                        semantic_type=_classify_child(child_text, section.semantic_groups),
                        page=section.page_number,
                        start_offset=abs_start + c_start,
                        end_offset=abs_start + c_end,
                        text=child_text,
                        is_parent=False,
                        parent_chunk_id=parent_id,
                        token_count=count_tokens(child_text),
                        is_table=section.is_table,
                        created_at=now,
                    )
                )
        return chunks
