"""Multi-step root-cause diagnosis agent (_04_Agent.md, Diagnosis Enhancement).

Implements the LangGraph diagnosis graph (§17):

    equipment resolver -> sensor retrieval -> health retrieval ->
    incident retrieval -> memory retrieval -> hypothesis generator ->
    evidence collector -> root-cause validator -> evidence scoring ->
    hypothesis ranking -> diagnosis synthesizer -> recommendation generator

Design principle (§18): the agent never jumps straight from symptoms to a
diagnosis. Every candidate cause is generated broadly, validated independently,
scored against weighted evidence, and only then ranked into a final diagnosis.

The LLM nodes require OpenAI: if it is unreachable the call raises
:class:`~rag.errors.OpenAIUnavailableError`, which propagates out of the graph as
a 503. The remaining keyword/data-grounded helpers are only a safety net for a
*successful but empty* LLM response, not an offline mode.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.state import DiagnosisState
from agents.tools import MaintenanceTools
from rag.llm import llm_client

logger = logging.getLogger(__name__)

# Evidence-scoring weights (_04_Agent.md §9).
_W_SENSOR = 0.40
_W_INCIDENT = 0.25
_W_MANUAL = 0.20
_W_MAINTENANCE = 0.10
_W_HEALTH = 0.05

# How far back to pull operational evidence (anomalies / faults / delays) so a
# diagnosis has corroborating history, not just the last 24h triage window.
_OPERATIONAL_WINDOW_HOURS = 24.0 * 14

# Offline-fallback symptom -> candidate failure modes (maximises recall, §4).
_SYMPTOM_CAUSES: dict[str, tuple[str, ...]] = {
    "vibration": ("Bearing Wear", "Shaft Misalignment", "Rotor Imbalance", "Loose Mounting"),
    "temperature": ("Lubrication Failure", "Cooling Fan Failure", "Bearing Wear", "Overload"),
    "overheat": ("Lubrication Failure", "Cooling Fan Failure", "Overload"),
    "hot": ("Lubrication Failure", "Cooling Fan Failure", "Overload"),
    "pressure": ("Blockage", "Seal Failure", "Valve Malfunction"),
    "current": ("Motor Overload", "Winding Fault", "Electrical Fault"),
    "rpm": ("Drive Belt Slippage", "Motor Fault", "Load Variation"),
    "speed": ("Drive Belt Slippage", "Motor Fault"),
    "noise": ("Bearing Wear", "Loose Component", "Gear Wear"),
    "leak": ("Seal Failure", "Gasket Failure"),
}
_RISK_HEALTH_SCORE = {"CRITICAL": 1.0, "HIGH": 0.8, "MEDIUM": 0.5, "LOW": 0.2}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


class DiagnosisAgent:
    """Compiled multi-step diagnosis graph plus a convenience ``run`` wrapper."""

    def __init__(self, tools: MaintenanceTools) -> None:
        self._tools = tools
        self._graph = self._build_graph()

    # -- public API ------------------------------------------------------
    async def run(
        self,
        *,
        equipment_id: str | None,
        equipment_code: str | None,
        equipment_type: str | None,
        equipment_name: str | None,
        symptoms: list[str],
        question: str,
    ) -> dict[str, Any]:
        initial: DiagnosisState = {
            "equipment_id": equipment_id,
            "equipment_code": equipment_code,
            "equipment_type": equipment_type,
            "equipment_name": equipment_name,
            "symptoms": symptoms,
            "question": question,
        }
        final: DiagnosisState = await self._graph.ainvoke(initial)
        return dict(final)

    # -- graph wiring (_04_Agent.md §17) ---------------------------------
    def _build_graph(self):
        g = StateGraph(DiagnosisState)
        g.add_node("retrieve_sensor", self._retrieve_sensor)
        g.add_node("retrieve_operational", self._retrieve_operational)
        g.add_node("retrieve_health", self._retrieve_health)
        g.add_node("retrieve_incidents", self._retrieve_incidents)
        g.add_node("retrieve_memory", self._retrieve_memory)
        g.add_node("generate_hypotheses", self._generate_hypotheses)
        g.add_node("collect_evidence", self._collect_evidence)
        g.add_node("validate", self._validate_hypotheses)
        g.add_node("score", self._score_evidence)
        g.add_node("rank", self._rank_hypotheses)
        g.add_node("synthesize", self._synthesize)
        g.add_node("recommend", self._recommend)
        g.add_node("compose", self._compose_report)

        g.add_edge(START, "retrieve_sensor")
        g.add_edge("retrieve_sensor", "retrieve_operational")
        g.add_edge("retrieve_operational", "retrieve_health")
        g.add_edge("retrieve_health", "retrieve_incidents")
        g.add_edge("retrieve_incidents", "retrieve_memory")
        g.add_edge("retrieve_memory", "generate_hypotheses")
        g.add_edge("generate_hypotheses", "collect_evidence")
        g.add_edge("collect_evidence", "validate")
        g.add_edge("validate", "score")
        g.add_edge("score", "rank")
        g.add_edge("rank", "synthesize")
        g.add_edge("synthesize", "recommend")
        g.add_edge("recommend", "compose")
        g.add_edge("compose", END)
        return g.compile()

    # -- retrieval nodes -------------------------------------------------
    async def _retrieve_sensor(self, state: DiagnosisState) -> dict[str, Any]:
        return {"sensor_summary": await self._tools.sensor_history(state.get("equipment_id"))}

    async def _retrieve_operational(self, state: DiagnosisState) -> dict[str, Any]:
        """Gather recent anomaly alerts, fault messages, delay logs and spares."""
        eid = state.get("equipment_id")
        anomalies = await self._tools.get_anomaly_alert(eid, number_of_records=15, hours=_OPERATIONAL_WINDOW_HOURS)
        faults = await self._tools.get_fault_error_messages(eid, hours=_OPERATIONAL_WINDOW_HOURS, number_of_records=20)
        delays = await self._tools.get_equipment_delay_log(eid, hours=_OPERATIONAL_WINDOW_HOURS, number_of_records=15)
        spares = await self._tools.get_spare_parts(eid, number_of_records=30)
        return {
            "anomalies": anomalies.get("rows", []),
            "faults": faults.get("rows", []),
            "delays": delays.get("rows", []),
            "spares": spares.get("rows", []),
        }

    async def _retrieve_health(self, state: DiagnosisState) -> dict[str, Any]:
        return {"health": await self._tools.equipment_health(state.get("equipment_id"))}

    async def _retrieve_incidents(self, state: DiagnosisState) -> dict[str, Any]:
        query = self._symptom_query(state)
        incidents = await self._tools.search_incidents(query, state.get("equipment_id"), k=6)
        return {"incidents": incidents}

    async def _retrieve_memory(self, state: DiagnosisState) -> dict[str, Any]:
        return {"memory_hits": await self._tools.episodic_memory(state.get("equipment_id"))}

    # -- hypothesis generator (_04_Agent.md §4-5) ------------------------
    async def _generate_hypotheses(self, state: DiagnosisState) -> dict[str, Any]:
        context = self._hypothesis_context(state)
        result = await llm_client.complete_json(
            "You are a maintenance engineer. Generate ALL plausible root causes "
            "for the reported symptoms. Do NOT select a final diagnosis. Maximise "
            "recall — missing a valid hypothesis is worse than an extra one. "
            "Return JSON only.",
            f"{context}\n\nReturn JSON: "
            '{"hypotheses":[{"cause":"...","confidence":0.0}]}',
            max_tokens=500,
        )
        hypotheses = self._parse_hypotheses(result)
        if not hypotheses:
            hypotheses = self._heuristic_hypotheses(state)
        hypotheses = self._apply_memory_prior(hypotheses, state.get("memory_hits", []))
        return {"hypotheses": hypotheses[:6]}

    def _parse_hypotheses(self, result: dict | None) -> list[dict[str, Any]]:
        if not result or not isinstance(result.get("hypotheses"), list):
            return []
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for h in result["hypotheses"]:
            if not isinstance(h, dict):
                continue
            cause = str(h.get("cause", "")).strip()
            if not cause or cause.lower() in seen:
                continue
            seen.add(cause.lower())
            try:
                conf = float(h.get("confidence", 0.5))
            except (ValueError, TypeError):
                conf = 0.5
            out.append({"cause": cause, "confidence": _clamp(conf)})
        return out

    def _heuristic_hypotheses(self, state: DiagnosisState) -> list[dict[str, Any]]:
        causes: dict[str, float] = {}

        # From historical incidents (strongest offline signal).
        for inc in state.get("incidents", []):
            cause = (inc.get("root_cause") or inc.get("failure_mode") or "").strip()
            if cause:
                causes[cause] = max(causes.get(cause, 0.0), 0.4 + 0.5 * inc.get("score", 0.0))

        # From symptom keywords.
        blob = " ".join(state.get("symptoms", []) + [state.get("question", "")]).lower()
        for keyword, mapped in _SYMPTOM_CAUSES.items():
            if keyword in blob:
                for cause in mapped:
                    causes.setdefault(cause, 0.5)

        if not causes:
            causes["Undetermined Fault"] = 0.3
        return [{"cause": c, "confidence": _clamp(s)} for c, s in
                sorted(causes.items(), key=lambda kv: kv[1], reverse=True)]

    @staticmethod
    def _apply_memory_prior(
        hypotheses: list[dict[str, Any]], memory_hits: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Boost hypotheses that match prior diagnoses for this equipment (§15)."""
        if not memory_hits:
            return hypotheses
        mem_blob = " ".join(m.get("diagnosis", "").lower() for m in memory_hits)
        for h in hypotheses:
            if h["cause"].lower() in mem_blob:
                h["confidence"] = _clamp(h["confidence"] + 0.1)
                h["memory_supported"] = True
        return hypotheses

    # -- evidence collector (_04_Agent.md §6) ----------------------------
    async def _collect_evidence(self, state: DiagnosisState) -> dict[str, Any]:
        equipment_id = state.get("equipment_id")
        symptom_text = self._symptom_query(state)
        sensor = state.get("sensor_summary", {})
        health = state.get("health")

        evidence: dict[str, list[dict[str, Any]]] = {}
        for h in state.get("hypotheses", []):
            cause = h["cause"]
            query = f"{cause} {symptom_text}".strip()
            items: list[dict[str, Any]] = []

            for m in await self._tools.search_manual(query, equipment_id, k=2):
                items.append({"type": "manual", "score": m["score"],
                              "details": self._snippet(m.get("concept"), m.get("text")),
                              "document_id": m.get("document_id"), "page": m.get("page")})
            for inc in await self._tools.search_incidents(query, equipment_id, k=2):
                items.append({"type": "historical_incident", "score": inc["score"],
                              "details": self._incident_details(inc),
                              "document_id": inc.get("document_id"), "page": inc.get("page")})
            for log in await self._tools.search_maintenance_logs(query, equipment_id, k=2):
                items.append({"type": "maintenance", "score": log["score"],
                              "details": self._log_details(log),
                              "document_id": log.get("document_id"), "page": log.get("page")})

            for breach in sensor.get("breaches", []):
                items.append({"type": "sensor", "score": 0.9 if breach["status"] == "CRITICAL" else 0.6,
                              "details": f"{breach['sensor_code']} {breach['status']} "
                                         f"(latest {breach['latest']}{breach.get('unit') or ''})"})
            for a in state.get("anomalies", [])[:5]:
                lvl = str(a.get("alert_level") or "").lower()
                items.append({"type": "anomaly", "score": 0.8 if lvl == "critical" else (0.5 if lvl == "warning" else 0.3),
                              "details": f"Anomaly {a.get('sensor_name')} {a.get('alert_level')} "
                                         f"dev {a.get('deviation_pct')}% — {a.get('probable_cause') or ''}"})
            for f in state.get("faults", [])[:5]:
                mt = str(f.get("message_type") or "").lower()
                items.append({"type": "fault", "score": 0.85 if mt in ("trip", "fault") else 0.5,
                              "details": f"Fault {f.get('fault_code')} [{f.get('message_type')}]: {f.get('message_text') or ''}"})
            for d in state.get("delays", [])[:4]:
                sev = str(d.get("severity") or "").lower()
                items.append({"type": "delay", "score": 0.7 if sev in ("critical", "high") else 0.3,
                              "details": f"Delay {d.get('delay_type')} ({d.get('severity')}): {d.get('cause_description') or ''}"})
            if health and health.get("risk_level"):
                items.append({"type": "health", "score": _RISK_HEALTH_SCORE.get(health["risk_level"], 0.3),
                              "details": f"Health score {health.get('health_score')}, "
                                         f"risk {health['risk_level']}, RUL {health.get('rul_days')}d"})
            evidence[cause] = items
        return {"evidence": evidence}

    # -- root-cause validator (_04_Agent.md §7-8) ------------------------
    async def _validate_hypotheses(self, state: DiagnosisState) -> dict[str, Any]:
        validations: dict[str, dict[str, Any]] = {}
        for h in state.get("hypotheses", []):
            cause = h["cause"]
            ev = state.get("evidence", {}).get(cause, [])
            validations[cause] = await self._validate_one(cause, ev, state)
        return {"validations": validations}

    async def _validate_one(
        self, cause: str, evidence: list[dict[str, Any]], state: DiagnosisState
    ) -> dict[str, Any]:
        ev_text = "\n".join(f"- [{e['type']}] {e.get('details', '')}" for e in evidence) or "None"
        result = await llm_client.complete_json(
            "You are a senior maintenance engineer. Evaluate whether the evidence "
            "supports the hypothesis. Do NOT generate new causes; only validate the "
            "provided one. Return JSON only.",
            f"Equipment: {state.get('equipment_code') or state.get('equipment_id')}\n"
            f"Symptoms: {self._symptom_query(state)}\n"
            f"Hypothesis: {cause}\nEvidence:\n{ev_text}\n\n"
            'Return JSON: {"support_score":0.0,"contradiction_score":0.0,'
            '"confidence":0.0,"reasoning":"...","supported":true}',
            max_tokens=300,
        )
        if result:
            return {
                "support_score": _clamp(float(result.get("support_score", 0.0) or 0.0)),
                "contradiction_score": _clamp(float(result.get("contradiction_score", 0.0) or 0.0)),
                "confidence": _clamp(float(result.get("confidence", 0.0) or 0.0)),
                "reasoning": str(result.get("reasoning", "")).strip(),
                "supported": bool(result.get("supported", True)),
            }
        return self._heuristic_validation(evidence)

    @staticmethod
    def _heuristic_validation(evidence: list[dict[str, Any]]) -> dict[str, Any]:
        if not evidence:
            return {"support_score": 0.1, "contradiction_score": 0.1, "confidence": 0.1,
                    "reasoning": "No supporting evidence retrieved.", "supported": False}
        strength = sum(e.get("score", 0.0) for e in evidence) / len(evidence)
        diversity = len({e["type"] for e in evidence}) / 5.0
        support = _clamp(0.6 * strength + 0.4 * diversity)
        return {"support_score": support, "contradiction_score": 0.1,
                "confidence": support, "supported": support >= 0.35,
                "reasoning": f"{len(evidence)} evidence items across "
                             f"{len({e['type'] for e in evidence})} sources."}

    # -- evidence scoring (_04_Agent.md §9) ------------------------------
    async def _score_evidence(self, state: DiagnosisState) -> dict[str, Any]:
        scores: dict[str, dict[str, float]] = {}
        hyp_conf = {h["cause"]: h.get("confidence", 0.5) for h in state.get("hypotheses", [])}
        for h in state.get("hypotheses", []):
            cause = h["cause"]
            ev = state.get("evidence", {}).get(cause, [])
            val = state.get("validations", {}).get(cause, {})

            sensor = self._max_score(ev, "sensor", default=0.2)
            incident = self._max_score(ev, "historical_incident")
            manual = self._max_score(ev, "manual")
            maintenance = self._max_score(ev, "maintenance")
            health = self._max_score(ev, "health", default=0.3)

            evidence_score = (
                _W_SENSOR * sensor + _W_INCIDENT * incident + _W_MANUAL * manual
                + _W_MAINTENANCE * maintenance + _W_HEALTH * health
            )

            # Blend with validator confidence and the generator's prior (§7-9).
            final = 0.6 * evidence_score + 0.25 * val.get("confidence", 0.3) + 0.15 * hyp_conf.get(cause, 0.5)
            if not val.get("supported", True):
                final *= 0.6
            final -= 0.2 * val.get("contradiction_score", 0.0)
            if h.get("memory_supported"):
                final += 0.05

            scores[cause] = {
                "sensor": round(sensor, 3), "incident": round(incident, 3),
                "manual": round(manual, 3), "maintenance": round(maintenance, 3),
                "health": round(health, 3), "evidence_score": round(evidence_score, 3),
                "final": round(_clamp(final), 3),
            }
        return {"scores": scores}

    @staticmethod
    def _max_score(evidence: list[dict[str, Any]], etype: str, default: float = 0.0) -> float:
        vals = [e.get("score", 0.0) for e in evidence if e.get("type") == etype]
        return _clamp(max(vals)) if vals else default

    # -- ranking (_04_Agent.md §10) --------------------------------------
    async def _rank_hypotheses(self, state: DiagnosisState) -> dict[str, Any]:
        scores = state.get("scores", {})
        ranked = sorted(
            ({"cause": c, "score": s["final"], "breakdown": s} for c, s in scores.items()),
            key=lambda r: r["score"], reverse=True,
        )
        return {"ranked": ranked}

    # -- synthesizer (_04_Agent.md §11, 13) ------------------------------
    async def _synthesize(self, state: DiagnosisState) -> dict[str, Any]:
        ranked = state.get("ranked", [])
        if not ranked:
            return {"diagnosis": "Undetermined", "confidence": 0.0,
                    "alternative_causes": [], "evidence_summary": [], "citations": []}

        top = ranked[0]
        alternatives = [{"cause": r["cause"], "confidence": r["score"]} for r in ranked[1:4]]
        evidence_summary, citations = await self._summarise_evidence(top["cause"], state)
        return {
            "diagnosis": top["cause"],
            "confidence": round(top["score"], 2),
            "alternative_causes": alternatives,
            "evidence_summary": evidence_summary,
            "citations": citations,
        }

    async def _summarise_evidence(
        self, cause: str, state: DiagnosisState
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        ev = sorted(state.get("evidence", {}).get(cause, []),
                    key=lambda e: e.get("score", 0.0), reverse=True)
        summary: list[dict[str, str]] = []
        citations: list[dict[str, Any]] = []
        seen_cite: set[tuple[str, Any]] = set()
        for e in ev[:6]:
            summary.append({"type": e["type"], "details": e.get("details", "")})
            doc_id = e.get("document_id")
            if doc_id:
                name = await self._tools.doc_name(doc_id)
                page = e.get("page") if isinstance(e.get("page"), int) else None
                key = (name, page)
                if key not in seen_cite:
                    seen_cite.add(key)
                    citations.append({"document": name, "page": page})
        return summary, citations

    # -- recommendation generator (_04_Agent.md §12) ---------------------
    async def _recommend(self, state: DiagnosisState) -> dict[str, Any]:
        diagnosis = state.get("diagnosis", "")
        ev = state.get("evidence", {}).get(diagnosis, [])
        ev_text = "\n".join(f"- [{e['type']}] {e.get('details', '')}" for e in ev) or "None"
        health = state.get("health") or {}
        spares = state.get("spares", [])
        spares_text = "\n".join(
            f"- {s.get('part_name')} (stock {s.get('current_stock')}, {s.get('stock_status')}, "
            f"lead {s.get('procurement_lead_time_days')}d)" for s in spares[:15]
        ) or "None on record"
        result = await llm_client.complete_json(
            "You are a maintenance engineer. Given a confirmed diagnosis, its "
            "evidence, the equipment's remaining-useful-life estimate, and the "
            "spare-parts inventory, generate concrete maintenance actions, the "
            "spare parts likely required (only from the inventory listed), and a "
            "short narrative estimate of how many more days the machine can run "
            "before it must be shut down. Return JSON only.",
            f"Equipment: {state.get('equipment_code') or state.get('equipment_id')} "
            f"({state.get('equipment_type')})\nDiagnosis: {diagnosis}\n"
            f"Deterministic RUL: {health.get('rul_days')} days; risk {health.get('risk_level')}\n"
            f"Evidence:\n{ev_text}\nSpare parts inventory:\n{spares_text}\n\n"
            'Return JSON: {"immediate_actions":[],"recommended_inspections":[],'
            '"recommended_repairs":[],"preventive_actions":[],'
            '"spare_parts_needed":[{"part":"...","stock_status":"...","lead_time_days":0}],'
            '"days_to_shutdown":"..."}',
            max_tokens=700,
        )
        if result:
            recs = {k: [str(x) for x in result.get(k, []) if x] for k in (
                "immediate_actions", "recommended_inspections",
                "recommended_repairs", "preventive_actions")}
            if any(recs.values()):
                spare_parts = result.get("spare_parts_needed") or self._heuristic_spares(state)
                days = str(result.get("days_to_shutdown") or self._heuristic_days_to_shutdown(state))
                return {"recommendations": recs, "spare_parts_needed": spare_parts, "days_to_shutdown": days}
        return {
            "recommendations": self._heuristic_recommendations(state),
            "spare_parts_needed": self._heuristic_spares(state),
            "days_to_shutdown": self._heuristic_days_to_shutdown(state),
        }

    @staticmethod
    def _heuristic_spares(state: DiagnosisState) -> list[dict[str, Any]]:
        """Fallback: surface the scarcest on-record parts for this equipment."""
        out: list[dict[str, Any]] = []
        for s in state.get("spares", []):
            if str(s.get("stock_status") or "").lower() in ("out of stock", "reorder required"):
                out.append({
                    "part": s.get("part_name"),
                    "stock_status": s.get("stock_status"),
                    "lead_time_days": s.get("procurement_lead_time_days"),
                })
        return out[:5]

    @staticmethod
    def _heuristic_days_to_shutdown(state: DiagnosisState) -> str:
        health = state.get("health") or {}
        rul = health.get("rul_days")
        if rul is None:
            return "Unknown — insufficient data to estimate remaining life."
        risk = health.get("risk_level") or "UNKNOWN"
        return f"Approximately {rul} days at current condition (risk {risk})."

    def _heuristic_recommendations(self, state: DiagnosisState) -> dict[str, list[str]]:
        diagnosis = state.get("diagnosis", "")
        immediate: list[str] = []
        inspections: list[str] = []
        repairs: list[str] = []
        preventive: list[str] = []

        for inc in state.get("incidents", []):
            res = (inc.get("resolution") or "").strip()
            if res and res not in repairs:
                repairs.append(res)
        for breach in state.get("sensor_summary", {}).get("breaches", []):
            immediate.append(
                f"Investigate {breach['sensor_code']} ({breach['status']} at {breach['latest']})."
            )
        health = state.get("health") or {}
        for action in health.get("preventive_actions", []):
            if action not in preventive:
                preventive.append(action)

        inspections.append(f"Inspect components associated with {diagnosis}.")
        if not repairs:
            repairs.append(f"Repair or replace the component implicated in {diagnosis}.")
        if not preventive:
            preventive.append("Schedule condition-based monitoring and lubrication checks.")
        return {
            "immediate_actions": immediate[:5] or [f"Assess severity of {diagnosis} before continued operation."],
            "recommended_inspections": inspections[:5],
            "recommended_repairs": repairs[:5],
            "preventive_actions": preventive[:5],
        }

    # -- report composer (final node) ------------------------------------
    async def _compose_report(self, state: DiagnosisState) -> dict[str, Any]:
        """Turn the structured diagnosis into a clean, templated report.

        This is the presentation layer. Rather than concatenating raw retrieved
        chunks, it forces the LLM to return a fixed JSON shape (summary +
        relevance-filtered evidence + alternative-cause reasoning) which is then
        rendered deterministically into markdown by :meth:`_render_markdown`.

        Crucially, the model is told that the retrieved-evidence list comes from
        similarity search and may contain items about a *different* failure mode,
        symptom or equipment, and must DROP anything that does not actually
        support the stated diagnosis. This fixes the prior behaviour where
        loosely-related incident chunks were surfaced verbatim as "evidence".

        On any LLM failure the node returns nothing, so callers fall back to the
        deterministic structured formatter instead of failing the whole turn.
        """
        diagnosis = state.get("diagnosis", "")
        if not diagnosis or diagnosis == "Undetermined":
            return {}

        evidence_summary = state.get("evidence_summary", [])
        ev_text = "\n".join(
            f"- [{e.get('type')}] {e.get('details', '')}" for e in evidence_summary
        ) or "None"
        alts = state.get("alternative_causes", [])
        alts_text = "\n".join(
            f"- {a.get('cause')} ({float(a.get('confidence', 0.0)):.0%})" for a in alts
        ) or "None"
        label = state.get("equipment_code") or state.get("equipment_id") or "the equipment"

        try:
            result = await llm_client.complete_json(
                "You are a senior maintenance engineer writing the final root-cause "
                "report that a plant operator reads directly. Be precise, grounded and "
                "concise. RULES: (1) Use ONLY facts present in the inputs — never invent "
                "sensor values, incidents, dates or part names. (2) The retrieved-evidence "
                "list comes from similarity search and MAY include items about a different "
                "failure mode, a different symptom, or different equipment. DROP every "
                "evidence item that does not directly support the stated diagnosis or does "
                "not match the reported symptoms — prefer a few solid points over many weak "
                "ones, and return an empty list if none truly fit. (3) Rewrite each kept "
                "item as ONE plain-language sentence. Return JSON only.",
                f"Equipment: {label} ({state.get('equipment_type') or 'unknown type'})\n"
                f"Reported symptoms: {self._symptom_query(state) or 'unspecified'}\n"
                f"Confirmed diagnosis: {diagnosis} "
                f"(confidence {float(state.get('confidence', 0.0)):.0%})\n"
                f"Alternative causes (ranked):\n{alts_text}\n"
                f"Retrieved evidence (filter for relevance):\n{ev_text}\n\n"
                'Return JSON: {"summary":"2-3 sentence plain-language explanation tying the '
                'reported symptoms to the diagnosis","key_evidence":["one plain-language '
                'sentence per RELEVANT evidence item"],"alternative_causes":[{"cause":"...",'
                '"why_less_likely":"one short reason it is less likely than the main diagnosis"}]}',
                max_tokens=900,
            )
        except Exception:  # never fail the turn on the cosmetic layer
            logger.exception("Report composition failed for %s; using structured fallback", label)
            return {}

        composed = self._parse_composition(result)
        if not composed:
            return {}
        return {"report_markdown": self._render_markdown(composed, state)}

    @staticmethod
    def _parse_composition(result: dict | None) -> dict[str, Any] | None:
        if not result:
            return None
        summary = str(result.get("summary", "")).strip()
        key_evidence = [
            str(e).strip() for e in (result.get("key_evidence") or []) if str(e).strip()
        ]
        alternatives: list[dict[str, str]] = []
        for a in result.get("alternative_causes") or []:
            if isinstance(a, dict) and str(a.get("cause", "")).strip():
                alternatives.append({
                    "cause": str(a["cause"]).strip(),
                    "why_less_likely": str(a.get("why_less_likely", "")).strip(),
                })
        if not summary and not key_evidence:
            return None
        return {"summary": summary, "key_evidence": key_evidence,
                "alternative_causes": alternatives}

    def _render_markdown(self, composed: dict[str, Any], state: DiagnosisState) -> str:
        """Render the composed sections into a fixed, scannable markdown template."""
        label = state.get("equipment_code") or state.get("equipment_id") or "the equipment"
        diagnosis = state.get("diagnosis", "Undetermined")
        confidence = float(state.get("confidence", 0.0))

        lines = [
            f"## Diagnosis: {diagnosis}",
            f"**Equipment:** {label}  |  **Confidence:** {confidence:.0%}",
            "",
        ]
        if composed.get("summary"):
            lines += [composed["summary"], ""]

        if composed.get("key_evidence"):
            lines.append("### Why we reached this conclusion")
            lines += [f"- {e}" for e in composed["key_evidence"]]
            lines.append("")

        if composed.get("alternative_causes"):
            lines.append("### Other causes considered")
            for a in composed["alternative_causes"]:
                why = a.get("why_less_likely")
                lines.append(f"- **{a['cause']}** — {why}" if why else f"- **{a['cause']}**")
            lines.append("")

        recs = state.get("recommendations", {})
        for header, key in (
            ("### Immediate actions", "immediate_actions"),
            ("### Recommended inspections", "recommended_inspections"),
            ("### Recommended repairs", "recommended_repairs"),
            ("### Preventive actions", "preventive_actions"),
        ):
            items = recs.get(key, [])
            if items:
                lines.append(header)
                lines += [f"- {item}" for item in items]
                lines.append("")

        spares = state.get("spare_parts_needed", [])
        if spares:
            lines.append("### Spare parts to line up")
            for s in spares:
                lines.append(f"- {self._format_spare(s)}")
            lines.append("")

        days = state.get("days_to_shutdown")
        if days:
            lines += ["### Operational outlook", str(days), ""]

        return "\n".join(lines).rstrip()

    @staticmethod
    def _format_spare(spare: Any) -> str:
        if not isinstance(spare, dict):
            return str(spare)
        part = spare.get("part") or spare.get("part_name") or "Unknown part"
        status = spare.get("stock_status")
        lead = spare.get("lead_time_days")
        if lead is None:
            lead = spare.get("procurement_lead_time_days")
        meta = ", ".join(
            x for x in [status, f"lead {lead}d" if lead is not None else None] if x
        )
        return f"{part} ({meta})" if meta else str(part)

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _symptom_query(state: DiagnosisState) -> str:
        symptoms = state.get("symptoms", [])
        if symptoms:
            return ", ".join(symptoms)
        return state.get("question", "")

    def _hypothesis_context(self, state: DiagnosisState) -> str:
        parts = [
            f"Equipment: {state.get('equipment_code') or state.get('equipment_id') or 'unknown'} "
            f"({state.get('equipment_type') or 'unknown type'})",
            f"Reported symptoms: {self._symptom_query(state) or 'unspecified'}",
        ]
        breaches = state.get("sensor_summary", {}).get("breaches", [])
        if breaches:
            parts.append("Sensor breaches: " + "; ".join(
                f"{b['sensor_code']} {b['status']} (latest {b['latest']})" for b in breaches))
        health = state.get("health")
        if health:
            parts.append(f"Health: score={health.get('health_score')}, risk={health.get('risk_level')}, "
                         f"predicted_failure={health.get('predicted_failure')}")
        anomalies = state.get("anomalies", [])
        if anomalies:
            parts.append("Recent anomaly alerts: " + "; ".join(
                f"{a.get('sensor_name') or '?'} {a.get('alert_level') or ''} "
                f"dev {a.get('deviation_pct')}% ({a.get('probable_cause') or '?'})"
                for a in anomalies[:5]))
        faults = state.get("faults", [])
        if faults:
            parts.append("Recent fault/alarm messages: " + "; ".join(
                f"{f.get('fault_code') or '?'} {f.get('message_type') or ''}: {f.get('message_text') or ''}"
                for f in faults[:5]))
        delays = state.get("delays", [])
        if delays:
            parts.append("Recent delays/breakdowns: " + "; ".join(
                f"{d.get('delay_type') or '?'} ({d.get('severity') or '?'}, "
                f"{d.get('duration_minutes')}min): {d.get('cause_description') or ''}"
                for d in delays[:5]))
        incidents = state.get("incidents", [])
        if incidents:
            parts.append("Similar historical incidents: " + "; ".join(
                f"{i.get('failure_mode') or '?'} -> {i.get('root_cause') or '?'}" for i in incidents[:4]))
        memory = state.get("memory_hits", [])
        if memory:
            parts.append("Past diagnoses for this equipment: " + "; ".join(
                m.get("diagnosis", "") for m in memory[:3]))
        return "\n".join(parts)

    @staticmethod
    def _snippet(concept: str | None, text: str | None, limit: int = 200) -> str:
        body = (text or "").strip().replace("\n", " ")
        if len(body) > limit:
            body = body[:limit].rstrip() + "..."
        return f"{concept}: {body}" if concept else body

    @staticmethod
    def _incident_details(inc: dict[str, Any]) -> str:
        return (f"Incident — failure: {inc.get('failure_mode') or '?'}, "
                f"root cause: {inc.get('root_cause') or '?'}, "
                f"resolution: {inc.get('resolution') or '?'}")

    @staticmethod
    def _log_details(log: dict[str, Any]) -> str:
        return (f"Maintenance log — symptom: {log.get('symptom') or '?'}, "
                f"action: {log.get('action') or '?'}, result: {log.get('result') or '?'}")
