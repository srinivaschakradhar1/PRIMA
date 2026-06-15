# Diagnosis Agent Architecture — Maintenance Wizard Backend

This document describes the **DiagnosisAgent**, the multi-step LangGraph that
performs root-cause analysis, and the reasoning behind each workflow decision. It
is delegated to by the [ConversationAgent](conversation-agent-architecture.md)
(diagnosis route) and is also reachable directly via `POST /agent/diagnose`. Code
references point at `src/agents/diagnosis.py`.

---

## 0. Foundational design decisions

Three principles shape the whole graph:

**Never jump from symptoms to a diagnosis.** The defining design rule: every
candidate cause is *generated broadly*, *validated independently*, *scored
against weighted evidence*, and only *then* ranked into a final diagnosis
(`diagnosis.py` module docstring, §18).

- *Why:* This mirrors how a senior engineer actually reasons — enumerate every
  plausible failure mode first, then let evidence eliminate or confirm each.
  Collapsing straight to "most likely" cause is exactly the shortcut that
  produces confident-but-wrong diagnoses. The graph structurally *separates*
  generation, validation, and selection into distinct nodes so no single LLM call
  can both invent and choose a cause.

**A linear 13-node retrieval → reasoning → synthesis → presentation pipeline.**
The graph is a straight chain (no branches), each node a small async function
returning a partial `DiagnosisState` that LangGraph shallow-merges
(`state.py:DiagnosisState`).

- *Why:* The reasoning is inherently sequential — you can't score evidence before
  you've collected it, can't rank before you've scored. A linear graph makes the
  data dependencies explicit and every intermediate (`hypotheses`, `evidence`,
  `validations`, `scores`, `ranked`) inspectable in the final state for debugging
  and auditing.

**LLM-required core, with deterministic safety nets for *empty* responses
only.** The hypothesis, validation, recommendation and report nodes call GPT; an
unreachable OpenAI raises `OpenAIUnavailableError` → 503. But a *successful but
empty/garbage* LLM response falls back to data-grounded heuristics.

- *Why:* This is a deliberate middle line (§17). It is *not* an offline mode — a
  diagnosis without the LLM would be too weak to trust, so the agent fails loud
  when OpenAI is genuinely down. But a momentary empty completion shouldn't blank
  out an answer when real sensor breaches, incidents and health data are sitting
  in the state, so each node degrades to a heuristic built from that data.

---

## 1. Graph overview

```
START
  ▼
retrieve_sensor ─▶ retrieve_operational ─▶ retrieve_health ─▶ retrieve_incidents ─▶ retrieve_memory
                                                                                        │
        ┌───────────────────────────────────────────────────────────────────────────┘
        ▼
generate_hypotheses ─▶ collect_evidence ─▶ validate ─▶ score ─▶ rank
                                                                  │
        ┌─────────────────────────────────────────────────────────┘
        ▼
synthesize ─▶ recommend ─▶ compose ─▶ END
```

Four phases: **retrieval** (5 nodes, gather all grounding data once),
**reasoning** (generate → collect → validate → score → rank), **synthesis**
(pick the winner, summarise evidence), and **presentation** (recommend + compose
the report).

---

## 2. Node-by-node workflow & decisions

### Phase 1 — Retrieval (nodes 1–5)

Five nodes gather every signal *before* any reasoning starts: 7-day sensor
summary (`retrieve_sensor`), a 14-day window of anomaly alerts / fault messages /
delay logs / spares (`retrieve_operational`), the latest health record
(`retrieve_health`), top-6 similar historical incidents (`retrieve_incidents`),
and prior validated diagnoses for this equipment (`retrieve_memory`).

- **Decision: front-load all retrieval into dedicated nodes before reasoning.**
  - *Importance:* The hypothesis generator and evidence collector then operate on
    a fully-populated state — they never have to stop and fetch. It also makes the
    grounding data a clean, inspectable snapshot in state.
- **Decision: a 14-day operational window** (`_OPERATIONAL_WINDOW_HOURS`),
  distinct from the conversation agent's 7-day triage view.
  - *Importance:* A diagnosis needs *corroborating history*, not just the last
    day's alarms. Two weeks of anomalies/faults/delays gives the evidence
    collector enough signal to confirm a slow-developing failure.
- **Decision: pull episodic memory** of past diagnoses for this equipment.
  - *Importance:* Feeds the memory-prior boost downstream — the agent leans toward
    causes it has correctly identified before on this same asset.

### Phase 2 — Reasoning

#### Node 6 — `generate_hypotheses` (maximise recall)

GPT is prompted to generate **ALL plausible root causes** and *explicitly told
not to pick a final diagnosis* ("missing a valid hypothesis is worse than an
extra one"). Output is parsed/deduped, falls back to
`_heuristic_hypotheses` (incident root-causes + a symptom→cause keyword map) on
empty, then `_apply_memory_prior` boosts causes matching past diagnoses (+0.10).
Capped at 6.

- **Decision: optimise for recall, not precision, at generation time.**
  - *Importance:* This is the heart of the "never jump to a diagnosis" principle.
    Precision is the job of the *later* validation/scoring nodes. A cause that's
    never hypothesised can never be selected, so the cost of omission is fatal
    while the cost of an extra candidate is just a little more evidence work.
- **Decision: memory prior as a small additive nudge (+0.10), not a hard
  override.**
  - *Importance:* Past success is a useful Bayesian prior but must not let history
    steamroll fresh contradicting evidence — so it only tilts, never decides.
- **Decision: heuristic fallback keyed on a symptom→failure-mode table.**
  - *Importance:* Keeps recall high even on an empty LLM response; the table
    encodes domain knowledge (vibration → bearing wear / misalignment / imbalance)
    so the fallback is still plausibly complete.

#### Node 7 — `collect_evidence` (per hypothesis)

For each hypothesis, a `"{cause} {symptoms}"` query gathers evidence from
**multiple independent sources**: equipment manuals, historical incidents,
maintenance logs (each via equipment-scoped hybrid search), plus sensor breaches,
anomaly alerts, fault messages, delay logs, and the health record. Each item
carries a `type` and a `score`.

- **Decision: per-hypothesis evidence gathering, scoped to the equipment.**
  - *Importance:* Evidence must be *about that cause* and *that asset* —
    cross-equipment retrieval is blocked at the vector-store level, so a
    hypothesis is never falsely "supported" by an unrelated machine's history.
- **Decision: fuse documentary evidence (RAG) with live operational signals.**
  - *Importance:* A manual says what *can* cause a fault; the sensor/anomaly/fault
    data says what's *actually happening now*. Scoring both lets a cause that the
    manual supports *and* the sensors corroborate rise above one supported by text
    alone. Source-type scores are hand-set by reliability (CRITICAL sensor breach
    0.9, trip fault 0.85, warning anomaly 0.5).

#### Node 8 — `validate` (independent per-cause judgement)

For each cause, GPT evaluates *only that hypothesis against its evidence* and is
*told not to generate new causes*, returning support/contradiction/confidence
scores + a `supported` boolean. Heuristic fallback scores by evidence strength ×
source diversity.

- **Decision: validation is a separate node, one cause at a time, generation
  forbidden.**
  - *Importance:* This enforces the generate/validate separation structurally. By
    judging each cause in isolation the agent gets an *independent* verdict per
    hypothesis instead of the LLM implicitly comparing and prematurely picking a
    winner. A `contradiction_score` lets evidence actively argue *against* a cause,
    not just fail to support it.
- **Decision: heuristic validation rewards source *diversity*, not just volume.**
  - *Importance:* Five sensor rows about the same channel is weaker corroboration
    than one sensor breach + one incident + one manual hit. Diversity across the
    five source types is a better proxy for genuine support.

#### Node 9 — `score` (weighted, multi-factor)

Each cause gets a weighted evidence score across source types — **sensor 0.40,
incident 0.25, manual 0.20, maintenance 0.10, health 0.05** — taking the *max*
score per type. The final score blends `0.6·evidence + 0.25·validator_confidence
+ 0.15·generator_prior`, then is penalised if unsupported (×0.6), reduced by
contradiction (−0.2·contradiction), and nudged for memory support (+0.05).

- **Decision: sensors weighted highest (0.40), historical incidents next (0.25).**
  - *Importance:* Live sensor data is the most direct, hardest-to-fake evidence of
    the *current* condition; past incidents on the same equipment are the next
    most predictive. Manuals (generic) and maintenance logs rank lower because
    they're less specific to the live fault. The weights encode an explicit
    evidence hierarchy.
- **Decision: blend evidence with validator confidence *and* the generator's
  prior, with explicit penalties.**
  - *Importance:* No single signal dominates. Evidence leads (0.6), but the
    independent validator (0.25) can pull down a cause that *looks* supported, and
    the unsupported/contradiction penalties make the validator's "no" actually
    bite. This is where precision is recovered after the high-recall generation.
- **Decision: take the *max* per source type, not the sum.**
  - *Importance:* One strong incident match shouldn't be diluted by several weak
    ones; the best evidence of each kind is what matters.

#### Node 10 — `rank`

Pure sort of causes by final score, descending, carrying the score breakdown.

- *Importance:* Keeps selection trivial and transparent — the ordered list (with
  per-source breakdown) is fully auditable.

### Phase 3 — Synthesis

#### Node 11 — `synthesize`

Top-ranked cause becomes the `diagnosis`; the next three become
`alternative_causes`. `_summarise_evidence` returns the top-6 evidence items for
the winner and deduped citations (resolved to document names).

- **Decision: always surface ranked alternatives, not just the winner.**
  - *Importance:* Maintenance is high-stakes; an engineer needs to see what else
    was considered and how close it scored. It also makes the diagnosis falsifiable
    — a wrong top pick with a strong runner-up is visibly low-confidence.

#### Node 12 — `recommend`

Given the confirmed diagnosis, its evidence, the deterministic RUL/risk, and the
**actual spares inventory**, GPT generates immediate actions, inspections,
repairs, preventive actions, the spare parts needed (*only from the listed
inventory*), and a narrative days-to-shutdown. Heuristic fallbacks cover each.

- **Decision: constrain spare-part recommendations to the on-record inventory.**
  - *Importance:* Recommending a part the plant doesn't stock is useless and
    erodes trust. Grounding the suggestion in the real inventory (with stock
    status + lead time) makes it actionable — the engineer learns immediately
    whether the fix is blocked on procurement.
- **Decision: feed the deterministic RUL into the narrative shutdown estimate.**
  - *Importance:* The remaining-useful-life number comes from the prediction
    engine, not the LLM — anchoring the narrative to it keeps the operational
    outlook grounded rather than invented.

### Phase 4 — Presentation

#### Node 13 — `compose` (relevance-filtered report)

The presentation layer. GPT rewrites the diagnosis into a fixed JSON shape
(summary + relevance-filtered key evidence + alternative-cause reasoning), which
`_render_markdown` renders deterministically into a scannable report. **The model
is explicitly told the retrieved evidence came from similarity search and may
include items about a different failure mode/symptom/equipment, and must DROP
anything that doesn't truly support the diagnosis.** On any failure the node
returns nothing, so the caller falls back to the structured formatter.

- **Decision: separate the *cosmetic* report layer from the *reasoning* layers,
  and let it fail safely.**
  - *Importance:* Composition is presentation only — if it errors it must never
    sink a turn that already has a valid structured diagnosis, hence the
    return-nothing-on-failure contract and the conversation agent's fallback.
- **Decision: a relevance filter at the final step that can drop "evidence".**
  - *Importance:* Fixes a real failure mode — similarity search surfaces
    loosely-related incident chunks, and earlier versions printed them verbatim as
    "evidence". Forcing the model to drop off-target items (and prefer a few solid
    points over many weak ones) keeps the report honest.
- **Decision: deterministic markdown rendering from a fixed JSON shape, not
  free-form LLM prose.**
  - *Importance:* The LLM decides *content*; the template decides *structure*. The
    operator always gets the same scannable sections (Diagnosis → Why → Other
    causes → Actions → Spares → Outlook), and the output can't drift into
    unpredictable formatting.

---

## 3. Summary of the "why" threads

| Decision | Rationale / importance |
|---|---|
| Never jump from symptoms to diagnosis | Generate → validate → score → rank, as separate nodes — prevents confident-but-wrong picks |
| Linear 13-node graph | Reasoning is inherently sequential; every intermediate is inspectable/auditable |
| LLM-required core, heuristics for *empty* responses only | Fail loud when OpenAI is down; don't blank an answer on a momentary empty completion |
| Front-load all retrieval (5 nodes) | Reasoning nodes operate on a complete, snapshotted state |
| 14-day operational window | Diagnosis needs corroborating history, not a 24h triage view |
| Hypotheses optimise for recall | A cause never generated can never be selected; precision comes later |
| Memory prior as +0.10 nudge | Useful prior without letting history override fresh evidence |
| Per-hypothesis, equipment-scoped evidence | Evidence must be about *that* cause and *that* asset; no cross-equipment "support" |
| Fuse documentary (RAG) + live operational signals | Manual says what *can* happen; sensors say what *is* happening |
| Independent per-cause validation, generation forbidden | Enforces generate/validate split; yields an independent verdict per cause |
| Weighted scoring (sensor 0.40 → health 0.05) | Explicit evidence hierarchy; live data outranks generic text |
| Blend evidence + validator + prior, with penalties | No single signal dominates; recovers precision after high-recall generation |
| Surface ranked alternatives | High-stakes domain; makes the diagnosis auditable and falsifiable |
| Spare-part recs constrained to real inventory | Actionable (stock + lead time); avoids recommending unstocked parts |
| Separate, fail-safe report composer | Presentation never sinks a valid diagnosis |
| Relevance filter that can drop evidence | Stops loosely-related similarity hits being printed as "evidence" |
| Deterministic markdown from fixed JSON | LLM picks content, template fixes structure — consistent, scannable reports |
