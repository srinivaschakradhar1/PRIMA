"""Search pipeline orchestrator (design §23-34).

    equipment detection -> intent detection -> metadata filtering ->
    multi-query expansion -> hybrid retrieval (dense + BM25 lexical, RRF-fused) ->
    historical incident retrieval -> hybrid ranking (semantic + lexical + metadata
    + equipment + recency) -> cross-encoder reranking -> parent-chunk expansion ->
    concept-graph expansion -> context compression -> GPT-4o.

Consumed by :class:`services.agent_service.AgentService` for /agent/chat and
/agent/diagnose. Degrades to deterministic extractive answers when GPT is
unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from rag.agents.intent_detection import (
    DetectedEquipment,
    EquipmentDetectionAgent,
    IntentDetectionAgent,
)
from rag.agents.query_expansion import QueryExpansionAgent
from rag.agents.reranking import cross_encoder_reranker
from rag.config import SETTINGS
from rag.embeddings import embedding_client
from rag.llm import llm_client
from rag.models import RetrievedItem
from rag.tokenization import count_tokens
from rag.vectorstore import DOCTYPE_TO_INDEX, vector_store

logger = logging.getLogger(__name__)

# Retrieval strategies: intent -> {index_name: weight} (design §34).
_STRATEGIES: dict[str, dict[str, float]] = {
    "DIAGNOSIS": {"failure_report_index": 0.40, "maintenance_log_index": 0.30,
                  "manual_index": 0.20, "sop_index": 0.10},
    "ROOT_CAUSE": {"failure_report_index": 0.40, "maintenance_log_index": 0.30,
                   "manual_index": 0.20, "sop_index": 0.10},
    "PROCEDURE": {"sop_index": 0.50, "manual_index": 0.30, "maintenance_log_index": 0.20},
    "MAINTENANCE_PLAN": {"maintenance_log_index": 0.40, "manual_index": 0.30,
                         "sop_index": 0.20, "failure_report_index": 0.10},
    "SPARE_PART": {"spare_part_index": 0.70, "manual_index": 0.20, "sop_index": 0.10},
    "GENERAL_QA": {"manual_index": 0.50, "sop_index": 0.20,
                   "failure_report_index": 0.15, "maintenance_log_index": 0.15},
}

# Always consult these for historical-incident retrieval (design §28).
_INCIDENT_INDEXES = {"failure_report_index": 0.10, "maintenance_log_index": 0.10}


@dataclass
class Citation:
    document: str
    page: int | None = None


@dataclass
class SearchAnswer:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    intent: str = "GENERAL_QA"
    equipment_code: str | None = None
    root_causes: list[tuple[str, float]] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    used_llm: bool = False


class SearchPipeline:
    def __init__(self, rag_repository, equipment_repository, knowledge_repository) -> None:
        self._repo = rag_repository
        self._equipment_repo = equipment_repository
        self._knowledge_repo = knowledge_repository
        self._equipment_agent = EquipmentDetectionAgent()
        self._intent_agent = IntentDetectionAgent()
        self._query_agent = QueryExpansionAgent()
        self._reranker = cross_encoder_reranker
        self._vs = vector_store

    # -- public API ------------------------------------------------------
    async def answer(
        self,
        question: str,
        equipment_id: str | None = None,
        intent_override: str | None = None,
        extra_context: str | None = None,
    ) -> SearchAnswer:
        # 1-2. Equipment + intent detection.
        detected = await self._detect_equipment(question, equipment_id)
        intent = intent_override or await self._intent_agent.run(question)

        # 3. Retrieval strategy (index set + weights), incl. incident indexes.
        weights = dict(_STRATEGIES.get(intent, _STRATEGIES["GENERAL_QA"]))
        for name, w in _INCIDENT_INDEXES.items():
            weights.setdefault(name, w)
        index_names = list(weights.keys())

        # 4. Multi-query expansion + 5. vector retrieval.
        queries = await self._query_agent.run(question, detected)
        items = await self._retrieve(queries, index_names, equipment_id)
        if not items:
            # No indexed documents matched, but live equipment data (health,
            # sensors, alerts, spares) may still answer the question.
            if extra_context:
                answer_text, used_llm = await self._generate_answer(
                    question, "", intent, extra_context
                )
                return SearchAnswer(
                    answer=answer_text,
                    citations=[],
                    intent=intent,
                    equipment_code=detected.equipment_code if detected else None,
                    confidence=0.4,
                    used_llm=used_llm,
                )
            return self._empty_answer(intent, detected)

        # 6. Hybrid ranking + 7. cross-encoder rerank.
        self._hybrid_rank(items, weights, detected)
        top = self._reranker.rerank(question, items, SETTINGS.rerank_top_k)

        # 8. Parent-chunk expansion + 9. concept-graph expansion.
        context_blocks, citations = await self._expand_and_cite(top)
        graph_lines = await self._graph_expansion(top, detected)

        # 10. Context compression + 11. answer generation.
        context = self._compress(context_blocks, graph_lines)
        answer_text, used_llm = await self._generate_answer(
            question, context, intent, extra_context
        )

        root_causes, actions = self._extract_diagnosis(top, graph_lines)
        confidence = self._confidence(top)

        return SearchAnswer(
            answer=answer_text,
            citations=citations,
            intent=intent,
            equipment_code=detected.equipment_code if detected else None,
            root_causes=root_causes,
            recommended_actions=actions,
            confidence=confidence,
            used_llm=used_llm,
        )

    async def diagnose(self, equipment_id: str, symptoms: list[str]) -> SearchAnswer:
        question = (
            f"Diagnose equipment {equipment_id} showing symptoms: "
            f"{', '.join(symptoms) if symptoms else 'unspecified'}. "
            "Identify the most likely root causes and corrective actions."
        )
        return await self.answer(question, equipment_id=equipment_id, intent_override="DIAGNOSIS")

    # -- pipeline steps --------------------------------------------------
    async def _detect_equipment(
        self, question: str, equipment_id: str | None
    ) -> DetectedEquipment | None:
        if equipment_id:
            equipment = await self._equipment_repo.get_by_id(equipment_id)
            if equipment:
                return DetectedEquipment(equipment.id, equipment.equipment_code, equipment.equipment_type)
        known = await self._equipment_repo.list_all()
        return self._equipment_agent.run(question, known)

    async def _retrieve(self, queries: list[str], index_names: list[str], equipment_id: str | None = None) -> list[RetrievedItem]:
        query_vectors = await embedding_client.embed(queries)
        best: dict[str, RetrievedItem] = {}
        for text, qv in zip(queries, query_vectors):
            # Hybrid dense + BM25 lexical retrieval (RRF-fused per index). The
            # lexical signal recovers exact codes / part numbers / fault codes
            # that dense embeddings under-weight.
            for hit in self._vs.hybrid_search(index_names, qv, text, SETTINGS.retrieval_top_k, equipment_id):
                key = f"{hit.index_name}:{hit.ref_id}"
                existing = best.get(key)
                if existing is None:
                    best[key] = hit
                else:
                    # Keep the strongest evidence of each kind seen across the
                    # expanded queries.
                    existing.semantic_score = max(existing.semantic_score, hit.semantic_score)
                    existing.lexical_score = max(existing.lexical_score, hit.lexical_score)
        return list(best.values())

    def _hybrid_rank(
        self,
        items: list[RetrievedItem],
        weights: dict[str, float],
        detected: DetectedEquipment | None,
    ) -> None:
        max_w = max(weights.values()) if weights else 1.0
        now = datetime.now(timezone.utc)
        for it in items:
            semantic = max(0.0, min(1.0, it.semantic_score))
            lexical = max(0.0, min(1.0, it.lexical_score))
            it.metadata_score = weights.get(it.index_name, 0.0) / max_w if max_w else 0.0
            it.equipment_score = self._equipment_score(it, detected)
            it.recency_score = self._recency_score(it.payload.get("created_at"), now)
            # Genuine hybrid score: dense + sparse(lexical) + metadata + equipment
            # + recency. Semantic stays dominant; lexical breaks ties on exact
            # code / part-number / fault-code matches dense retrieval misses.
            it.final_score = (
                0.35 * semantic
                + 0.15 * lexical
                + 0.25 * it.metadata_score
                + 0.15 * it.equipment_score
                + 0.10 * it.recency_score
            )

    @staticmethod
    def _equipment_score(it: RetrievedItem, detected: DetectedEquipment | None) -> float:
        if detected is None:
            return 0.5
        eid = it.payload.get("equipment_id")
        if eid == detected.equipment_id:
            return 1.0
        return 0.4 if eid is None else 0.0

    @staticmethod
    def _recency_score(created_at: str | None, now: datetime) -> float:
        if not created_at:
            return 0.5
        try:
            ts = datetime.fromisoformat(created_at)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
            return 1.0 / (1.0 + age_days / 30.0)
        except (ValueError, TypeError):
            return 0.5

    async def _expand_and_cite(
        self, top: list[RetrievedItem]
    ) -> tuple[list[str], list[Citation]]:
        blocks: list[str] = []
        citations: list[Citation] = []
        seen_parents: set[str] = set()
        doc_names: dict[str, str] = {}

        for it in top:
            payload = it.payload
            doc_id = payload.get("document_id")
            doc_name = await self._doc_name(doc_id, doc_names)
            page = payload.get("page")

            if it.kind == "chunk":
                # Parent-chunk expansion: retrieve the full concept for context.
                parent_id = payload.get("parent_chunk_id")
                text = payload.get("text", "")
                if parent_id and parent_id not in seen_parents:
                    parent = await self._repo.get_chunk(parent_id)
                    if parent:
                        text = parent.get("text", text)
                        page = parent.get("page", page)
                        seen_parents.add(parent_id)
                concept = payload.get("concept") or "Concept"
                blocks.append(f"[{doc_name} | {concept}]\n{text.strip()}")
            else:
                label = "Historical incident" if it.kind == "incident" else "Maintenance record"
                blocks.append(f"[{doc_name} | {label}]\n{payload.get('text', '').strip()}")

            citation = Citation(document=doc_name, page=page if isinstance(page, int) else None)
            if citation not in citations:
                citations.append(citation)
        return blocks, citations

    async def _graph_expansion(
        self, top: list[RetrievedItem], detected: DetectedEquipment | None
    ) -> list[str]:
        concepts = {
            it.payload.get("concept") for it in top if it.payload.get("concept")
        }
        rels = await self._repo.get_relationships_for_concepts(
            detected.equipment_id if detected else None, list(concepts)
        )
        return [f"{r['source']} --{r['relation']}--> {r['target']}" for r in rels]

    def _compress(self, context_blocks: list[str], graph_lines: list[str]) -> str:
        budget = SETTINGS.context_max_tokens
        parts: list[str] = []
        used = 0
        if graph_lines:
            graph_text = "KNOWLEDGE GRAPH:\n" + "\n".join(graph_lines[:30])
            graph_tokens = count_tokens(graph_text)
            if graph_tokens < budget // 3:
                parts.append(graph_text)
                used += graph_tokens
        for block in context_blocks:
            tokens = count_tokens(block)
            if used + tokens > budget:
                remaining = budget - used
                if remaining > 50:
                    parts.append(block[: remaining * 4])
                break
            parts.append(block)
            used += tokens
        return "\n\n---\n\n".join(parts)

    async def _generate_answer(
        self, question: str, context: str, intent: str, extra_context: str | None = None
    ) -> tuple[str, bool]:
        system = (
            "You are an expert industrial maintenance engineer for a steel plant. "
            "Answer using the provided context: live equipment data (current health, "
            "recent sensor status, anomaly alerts, fault messages and spare-parts "
            "inventory) and retrieved documents (equipment manuals, SOPs, failure "
            "reports, maintenance logs and a knowledge graph). Prefer the live data "
            "for questions about current condition. Be specific and actionable. Cite "
            "source document names in square brackets. If the context is insufficient, "
            "say so."
        )
        live = f"Live equipment data:\n{extra_context}\n\n" if extra_context else ""
        user = f"Question ({intent}):\n{question}\n\n{live}Context:\n{context}"
        text = await llm_client.complete_text(system, user, max_tokens=900)
        return text.strip(), True

    def _extract_diagnosis(
        self, top: list[RetrievedItem], graph_lines: list[str]
    ) -> tuple[list[tuple[str, float]], list[str]]:
        root_causes: list[tuple[str, float]] = []
        actions: list[str] = []
        seen_causes: set[str] = set()
        seen_actions: set[str] = set()

        for it in top:
            payload = it.payload
            if it.kind == "incident":
                cause = (payload.get("root_cause") or "").strip()
                if cause and cause.lower() not in seen_causes:
                    seen_causes.add(cause.lower())
                    root_causes.append((cause, round(min(1.0, max(0.0, it.final_score)), 2)))
                res = (payload.get("resolution") or "").strip()
                if res and res.lower() not in seen_actions:
                    seen_actions.add(res.lower())
                    actions.append(res)

        for line in graph_lines:
            if "--HAS_CAUSE-->" in line:
                cause = line.split("--HAS_CAUSE-->")[-1].strip()
                if cause.lower() not in seen_causes:
                    seen_causes.add(cause.lower())
                    root_causes.append((cause, 0.5))
            elif "--CORRECTED_BY-->" in line or "--PREVENTED_BY-->" in line:
                action = line.split("-->")[-1].strip()
                if action.lower() not in seen_actions:
                    seen_actions.add(action.lower())
                    actions.append(action)

        return root_causes[:5], actions[:5]

    @staticmethod
    def _confidence(top: list[RetrievedItem]) -> float:
        if not top:
            return 0.0
        return round(min(1.0, max(0.0, top[0].final_score)), 2)

    def _empty_answer(self, intent: str, detected: DetectedEquipment | None) -> SearchAnswer:
        return SearchAnswer(
            answer=(
                "No indexed maintenance knowledge matched this question yet. "
                "Upload relevant manuals, SOPs or failure reports for this equipment."
            ),
            intent=intent,
            equipment_code=detected.equipment_code if detected else None,
        )

    async def _doc_name(self, doc_id: str | None, cache: dict[str, str]) -> str:
        if not doc_id:
            return "unknown"
        if doc_id in cache:
            return cache[doc_id]
        doc = await self._knowledge_repo.get_by_id(doc_id)
        name = doc.document_name if doc and doc.document_name else doc_id
        cache[doc_id] = name
        return name
