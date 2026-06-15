"""Multi Query Expansion Agent (design §26).

Generates paraphrases / related queries for the original question so retrieval
covers more of the relevant concept space. Always includes the original query.
Requires OpenAI; raises :class:`~rag.errors.OpenAIUnavailableError` when it is
unavailable (no offline fallback).
"""

from __future__ import annotations

from rag.agents.intent_detection import DetectedEquipment
from rag.llm import llm_client


class QueryExpansionAgent:
    async def run(
        self, question: str, equipment: DetectedEquipment | None, max_queries: int = 5
    ) -> list[str]:
        result = await llm_client.complete_json(
            "You expand maintenance search queries.",
            f"Generate {max_queries - 1} alternative search queries for retrieval "
            f"that capture the same intent as the question, using equipment and "
            f"failure-mode terminology.\nQuestion: {question}\n"
            'Return JSON only: {"queries": ["...", "..."]}',
            max_tokens=300,
        )
        queries = [question]
        for q in result.get("queries", []) or []:
            q = str(q).strip()
            if q and q.lower() not in {x.lower() for x in queries}:
                queries.append(q)
        return queries[:max_queries]
