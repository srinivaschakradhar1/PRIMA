# Conversation Agent Architecture — Maintenance Wizard Backend

This document describes the **ConversationAgent**, the LangGraph orchestrator
behind `POST /agent/chat`, and the reasoning behind each workflow decision. It is
the entry point an engineer talks to: it guards scope, builds context, detects
intent, routes to one of three specialized agents, writes memory, and assembles
the reply. Code references point at `src/agents/`.

---

## 0. Foundational design decisions

Four choices shape the whole workflow:

**A compiled LangGraph state machine, not ad-hoc control flow.** The agent is a
`StateGraph(ConversationState)` compiled once and reused (`conversation.py`).
Each node returns a *partial* dict that LangGraph shallow-merges into a shared
`TypedDict` state (`state.py`).

- *Why:* Nodes stay small and independently testable; they only return the keys
  they produce. The graph topology *is* the documented workflow
  (`START → scope_guard → context_builder → intent_detection → agent_router →
  {general|equipment|diagnosis} → memory_writer → response_generator → END`), so
  the control flow is declarative and auditable rather than buried in branching
  code.

**Equipment is mandatory and resolved once, up front.** The engineer selects the
equipment in the UI; `equipment_code` is required and passed into the initial
state (`chat()`). The orchestrator never resolves or confirms equipment mid-turn.

- *Why:* It eliminates an entire class of ambiguity ("which pump did you mean?")
  and a round-trip of confirmation turns. Every tool and persisted health record
  keys on the equipment *code*, so fixing it at the boundary keeps the rest of
  the graph simple and deterministic. (The code is the canonical key;
  `MaintenanceTools._equipment_code` maps internal ids to codes for the
  operational tables.)

**Stateless API, conversation reconstructed from `conversation_history`.** The
endpoint holds no server-side session. Every turn re-sends the prior turns, and
the agent recovers protocol state (e.g. "am I mid-probe?") by inspecting the
*echoed* history.

- *Why:* Horizontal scalability and crash-resilience — any worker can serve any
  turn. The cost is that multi-turn protocols must encode their state *in the
  messages themselves* (see the symptom-probe marker below), which the design
  does deliberately.

**LLM-first with a deterministic heuristic fallback at every decision.** Scope,
intent, symptom extraction, and co-occurring-symptom selection all try GPT first
and fall back to keyword/structural heuristics on `OpenAIUnavailableError`.

- *Why:* Unlike the RAG retrieval core (which refuses to degrade), the
  *conversational routing* layer must never crash a turn. A slightly worse intent
  guess is acceptable; a 500 on every chat is not. The fallbacks **fail open** —
  ambiguous input is allowed through and answered.

---

## 1. Graph overview

```
                    ┌──────────────┐
        START ──▶   │  scope_guard │ ──(blocked)──────────────────┐
                    └──────┬───────┘                              │
                           │ (continue)                           ▼
                  ┌────────────────┐                     ┌──────────────────┐
                  │ context_builder│                     │ response_generator│ ──▶ END
                  └────────┬───────┘                     └──────────────────┘
                           ▼                                       ▲
                  ┌────────────────┐                              │
                  │ intent_detection│                             │
                  └────────┬───────┘                              │
                           ▼                                       │
                  ┌────────────────┐                              │
                  │  agent_router  │                              │
                  └───┬────┬────┬──┘                              │
              general │    │    │ diagnosis                        │
                      ▼    ▼    ▼                                  │
            ┌─────────┐ ┌─────────┐ ┌──────────┐                  │
            │ general │ │equipment│ │diagnosis │                  │
            │  agent  │ │  agent  │ │  agent   │                  │
            └────┬────┘ └────┬────┘ └────┬─────┘                  │
                 └───────────┼───────────┘                        │
                             ▼                                     │
                    ┌────────────────┐                            │
                    │  memory_writer │ ───────────────────────────┘
                    └────────────────┘
```

Two conditional edges drive the branching: `_after_guard` (blocked vs continue)
and `_pick_agent` (general / equipment / diagnosis).

---

## 2. Node-by-node workflow & decisions

### Node 0 — `scope_guard` (content guardrail, runs *first*)

A `ScopeGuard` (`guardrail.py`) decides whether the message is within the
steel-plant maintenance domain. Off-topic messages skip the entire pipeline and
route straight to `response_generator` with a fixed `REFUSAL_MESSAGE`.

- **Decision: guardrail as the first node, not a wrapper around the LLM call.**
  Off-topic requests never touch retrieval, diagnosis, or external tools.
  - *Importance:* Saves tokens and tool calls, keeps answers grounded in-domain,
    and gives a consistent refusal. Putting it *inside* the graph (rather than in
    the API layer) means it shares the same state and equipment context.
- **Decision: LLM classifier + keyword fallback that *fails open*.** Trivial
  follow-ups (`yes`, `why`, ≤2 words) are always allowed; on LLM failure the
  heuristic blocks only *clearly* off-topic input and lets ambiguity through.
  - *Importance:* A steel-plant question phrased unusually should never be
    wrongly refused. Over-refusing is a worse failure than occasionally letting a
    borderline message through, so the bias is intentional.

### Node 1 — `context_builder`

Normalizes `conversation_history` into clean `{role, content}` dicts and computes
one derived signal: `is_affirmation` (the message is a bare "yes/correct/ok"…).

- **Decision: detect affirmations here, once.** A bare "yes" is meaningless alone
  — it only continues a *prior* intent.
  - *Importance:* This flag is what lets a confirmation turn ("yes, diagnose it")
    inherit the previous intent and reuse the earlier symptom-bearing message,
    instead of being misrouted as a fresh general question.

### Node 2 — `intent_detection`

Classifies the message into `GENERAL_PLANT_QUESTION`, `EQUIPMENT_QUESTION`,
`DIAGNOSIS_REQUEST`, or `UNKNOWN`.

- **Decision: a protocol short-circuit before any classification.** If the most
  recent assistant turn was a co-occurring-symptom probe, this turn *is* the
  answer to it → force `DIAGNOSIS` at confidence 0.9.
  - *Importance:* Intent detection otherwise sees only the bare message (no
    history), so a reply like "yes" would misroute to the general agent and
    abandon the in-progress diagnosis. The protocol state is recovered purely
    from the echoed history — the stateless-API tax, paid explicitly.
- **Decision: LLM classifier, heuristic fallback.** The heuristic scores
  symptom/spec/general keyword hits, and adds weight to spec-question openers
  ("what is its operating temperature?") so a *factual* question that merely
  names a metric isn't mistaken for a *symptom*.
  - *Importance:* The distinction between "what's the normal temperature?"
    (equipment fact) and "the temperature is rising" (diagnosis) is the crux of
    routing; the opener bonus encodes that boundary deterministically.

### Node 3 — `agent_router`

Pure mapping from intent → route (`diagnosis` / `equipment` / `general`), with
`UNKNOWN` defaulting to `general`. `_pick_agent` is the conditional edge.

- **Decision: routing is a separate, side-effect-free node.**
  - *Importance:* Keeps the routing table in one place and makes the three agents
    interchangeable leaves of the graph — easy to add a fourth later.

### Live equipment grounding (shared by the Q&A agents)

`_equipment_context` assembles a compact markdown snapshot from
`MaintenanceTools`: current health (score / risk / RUL / predicted failure),
7-day sensor breaches, recent anomaly alerts, fault/alarm messages, and
spare-parts inventory.

- **Decision: reuse the prediction agent's operational tools to ground the RAG
  answer with *live* data.**
  - *Importance:* Documents alone can't answer "is it healthy *now*?" or "do we
    have the spare in stock?". Injecting live state alongside retrieved documents
    (and instructing GPT to *prefer* live data for current-condition questions)
    is what makes the assistant operational rather than just a manual search.

### Node 4a — `general_agent` (General Plant Knowledge)

Delegates to the RAG `SearchPipeline.answer()` with the live snapshot as
`extra_context`, no equipment filter.

- **Decision: reuse the RAG pipeline rather than a bespoke retriever.** Plant-wide
  policy/safety/SOP questions aren't equipment-scoped.
  - *Importance:* One retrieval implementation, one place for hybrid search /
    reranking / citations. The agent layer stays thin.

### Node 4b — `equipment_agent` (Equipment Knowledge)

Same as general, but passes `equipment_id` (scoping retrieval to that asset) and
`intent_override="GENERAL_QA"`.

- **Decision: hard-scope retrieval to the selected equipment.**
  - *Importance:* A spec answer must never bleed in another asset's manual.
    Equipment isolation happens at the vector-store level (payload filtering
    before ranking), so cross-equipment evidence is structurally impossible here.

### Node 4c — `diagnosis_agent` (multi-step root-cause analysis)

The richest node. It extracts symptoms, optionally runs a **co-occurring-symptom
probe**, then delegates to the multi-step `DiagnosisAgent` graph and formats the
report.

1. **Effective question.** If the turn is a bare affirmation, the symptoms live
   in the *prior* user turn, so that earlier message becomes the effective
   diagnosis question (`_effective_question`).
2. **Symptom extraction** (`_extract_symptoms`). LLM extracts every distinct
   symptom across the current message *and* earlier user turns; keyword heuristic
   fallback otherwise.
   - *Decision/why:* Engineers state symptoms across turns ("bearing is
     vibrating" … later "yes, diagnose it"). Feeding prior user messages avoids
     losing symptoms mentioned earlier.
3. **The co-occurring-symptom probe** — the signature workflow decision:
   - *Before* diagnosing, the agent pulls **past-incident symptom *sets*** for
     this equipment (`historical_symptom_groups`) — each set being symptoms
     observed *together* in one past incident — and asks the LLM which historical
     symptoms tend to co-occur with what the engineer reported. It surfaces up to
     5 as a one-time probe ("Before I diagnose, have you also noticed any of
     these…?").
   - The probe is gated to run **at most once per conversation** (`_already_probed`),
     and the *next* turn is recognized as the answer (`_awaiting_symptom_confirmation`)
     via a marker string embedded in the probe text (`_SYMPTOM_PROBE_MARKER`).
   - **Decision: ask about forgotten symptoms, and reason over symptom *groups*,
     not a flat pool.**
     - *Importance:* Under-reported symptoms are the top cause of misdiagnosis. A
       symptom is only worth suggesting because it historically appeared
       *alongside* something currently observed — co-occurrence, not raw
       frequency, is the signal. The deterministic fallback preserves this:
       it prefers symptoms from incidents that *share* a reported symptom, only
       falling back to most-broadly-associated symptoms when nothing overlaps.
   - **Decision: cap at one probe and encode probe-state in the message marker.**
     - *Importance:* Guarantees the protocol can never loop (the turn after a
       probe always proceeds to diagnosis) and works on a stateless API — the
       only durable signal is the assistant message echoed back. The marker is
       deliberately kept clear of the word "diagnosis" so the feedback heuristic
       can't misfire on the answer turn.
4. **Confirmation folding** (`_confirmed_extra_symptoms`). When the turn answers a
   probe, the LLM decides which candidates the engineer confirmed (+ any new
   ones); heuristic fallback handles bare "yes" (→ all), "no" (→ none), and
   substring mentions.
5. **Delegation.** Calls `DiagnosisAgent.run(...)` (its own LangGraph: retrieve →
   hypothesize → gather evidence → validate → score/rank → synthesize → compose).
   The conversation agent formats the returned `report_markdown`, falling back to
   a structured concatenation if composition was skipped.
   - **Decision: diagnosis is a *separate* graph delegated to, not inlined.**
     - *Importance:* Keeps the conversation orchestrator focused on dialogue
       management; the heavy multi-step reasoning lives in `diagnosis.py` and is
       reusable by `POST /agent/diagnose` directly.

### Node 5 — `memory_writer`

Writes episodic memory and an optional feedback signal.

- **Decision: store validated diagnoses as episodic memory (outcome `PENDING`).**
  - *Importance:* Future diagnosis requests for the same equipment can be
    memory-assisted (`episodic_memory` tool) — the agent learns from its own past
    conclusions rather than re-deriving from scratch.
- **Decision: infer feedback automatically from the conversation flow**
  (`_maybe_write_feedback`). If the prior assistant turn was a diagnosis and the
  engineer's reply starts with a negation → `DIAGNOSIS_REJECTED`; an affirmation
  or "how do I…" follow-up → `DIAGNOSIS_CONFIRMED`.
  - *Importance:* Captures a real-world correctness signal with zero extra UI —
    a "how do I do that?" reply is implicit confirmation the diagnosis was
    actionable. This feeds the outcome history that future hypothesis ranking can
    weight.

### Node 6 — `response_generator`

The single exit node. Returns `response`, `citations`, `equipment_code`, and a
stable `agent_trace_id`. Blocked turns (from the guard) arrive here directly.

- **Decision: one terminal node for every path (answered, refused, errored).**
  - *Importance:* Guarantees a well-formed response shape and a trace id on every
    turn regardless of how it was handled — refusals, answers, and fallbacks all
    look identical to the caller.

---

## 3. Summary of the "why" threads

| Decision | Rationale / importance |
|---|---|
| Compiled LangGraph state machine | Topology *is* the documented workflow; small, testable nodes |
| Equipment mandatory & fixed up front | Removes ambiguity and confirmation round-trips; one canonical key everywhere |
| Stateless API, state from echoed history | Horizontal scale & crash-resilience; protocols encode state in messages |
| LLM-first + fail-open heuristics | Routing must never crash a turn; ambiguity is allowed through |
| Guardrail as first node | Off-topic input never reaches tools/retrieval; consistent refusal |
| Affirmation detection in context builder | Lets "yes" inherit prior intent & reuse earlier symptoms |
| Protocol short-circuit in intent detection | A probe answer continues diagnosis instead of misrouting |
| Spec-opener bonus in intent heuristic | Separates "what's normal?" (fact) from "it's rising" (symptom) |
| Reuse RAG `SearchPipeline` for Q&A | One retrieval stack; thin agent layer |
| Live equipment grounding | Answers current-condition / spares questions documents can't |
| Co-occurring-symptom probe over symptom *groups* | Counters under-reporting; co-occurrence (not frequency) is the signal |
| One-probe cap + message marker | Loop-proof multi-turn protocol on a stateless API |
| Diagnosis delegated to its own graph | Keeps orchestrator dialogue-focused; reusable reasoning engine |
| Episodic memory + auto-inferred feedback | Learns from past diagnoses; captures correctness signal with no extra UI |
| Single terminal response node | Uniform response shape + trace id on every path |
