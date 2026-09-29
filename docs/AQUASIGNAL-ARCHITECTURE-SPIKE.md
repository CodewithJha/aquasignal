# AquaSignal — Architecture / Product Discovery Spike

**Date:** 22 Sep 2026 (IST)  
**Role:** Principal software architect + environmental-data systems engineer (hostile)  
**Scope:** Architecture / product decision only. **NO implementation. NO PoC. NO UI.**  
**Workspace:** this repository  
**Priors challenged:** ConfirmGate-as-sole-hero; proposed full AquaSignal continuous multi-source platform; claim that ConfirmGate shrinks to ~5–10% of product  
**Legend:** **[FACT]** repo/OAH-cited · **[INFERENCE]** reasoned · **[UNKNOWN]** needs organizer/data confirmation · **[VERIFY]** must check against IG/protocols/licenses before claiming

**Deadline context:** Submit **29 Sep 2026**; hard clock **30 Sep 2026 9:00 PM PDT = 1 Oct 2026 09:30 IST**. Calendar distance from this spike ≈ **7 days**. **[FACT]** `AGENTS.md`, hackathon rules via ConfirmGate spike.

> Dates in this spike reflect the original schedule. Current Devpost deadline: **4 Oct 2026, 9:00 PM PDT (5 Oct 2026, 09:30 IST)**.

---

## Sources inspected (ConfirmGate repo)

| Path | Role | Label |
|---|---|---|
| `docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md` | ConfirmGate BUILD authority | **[FACT]** |
| `docs/PHASE1-AUDIT.md` | Historical scaffold audit (superseded by Phases 2–8 code) | **[FACT]** dated; code has moved on |
| `docs/DOMAIN-MODEL.md`, `docs/FLAG-ENGINE.md`, `docs/FHIR-SPEC.md`, `docs/PERSISTENCE.md`, `docs/HITL-POLICY.md`, `docs/AI-POLICY.md`, `docs/PRD.md`, `docs/REQUIREMENTS.md`, `docs/UX-SPEC.md` | Active ConfirmGate contracts | **[FACT]** |
| `app/domain/*` | `ObservationPacket` aggregate, state machine, VOs | **[FACT]** |
| `app/flags/*` | `DeterministicFlagEngine` + modular rules | **[FACT]** |
| `app/application/*` | Citizen/reviewer flows, ports, HITL audit | **[FACT]** |
| `app/persistence/*` | SQLite + migrations + UoW | **[FACT]** |
| `app/fhir/*` | Finalize-only exporter, TemporaryOahSystem registry | **[FACT]** |
| `app/ai/*` | `AiAssistPort` + Null/Fake/optional HTTP | **[FACT]** |
| `app/web/*`, `app/templates/*` | SSR `/upload`, `/observation`, `/review`, `/fhir` | **[FACT]** |
| `tests/` | **196** collected tests | **[FACT]** `pytest --collect-only` 22 Sep 2026 |
| OAH hubs (CS, Resilience Map, GEOSSIP, FHIR IG, factsheets/protocols) | Ecosystem boundary | **[FACT]** URLs in `AGENTS.md` / spike |

---

# PART 0 — ConfirmGate repository map (discovery)

## 0.1 What exists today (honest inventory)

ConfirmGate Phases **1–8 are implemented** as a modular FastAPI monolith. README still says “Phase 1 architecture cleanup” — **documentation lag**, not product truth. **[FACT]** code + phase docs vs `README.md` L7.

| Layer | Location | Responsibility |
|---|---|---|
| Entrypoint | `app/main.py` | Thin FastAPI; title ConfirmGate; mounts static + routes |
| Composition | `app/composition.py` | Wires FlagEngine, SQLite UoW, Null/Fake/HTTP AI, flows |
| Domain | `app/domain/` | `ObservationPacket`, `WorkflowState`, `SiteRef`, `FieldValue`, `QualityFlag`, provenance intents |
| Flags | `app/flags/` | Pure deterministic rules; no trust score; versioned `FLAG_RULES_VERSION` |
| Application | `app/application/` | `ObservationService`, `CitizenFlowService`, `ReviewerFlowService`, ports, audit |
| Persistence | `app/persistence/` | SQLite schema v1, repos, migrations, duplicate lookup |
| Provenance | Domain intents → durable `provenance_events`; `app/provenance/log.py` thin | Append-only |
| FHIR | `app/fhir/` | StructuralGuard → mapper → refuse-unless-FINALIZED; never `preliminary` |
| AI | `app/ai/` | Suggestions/explanations only; Null required |
| Web | `app/web/` + Jinja templates | Citizen + reviewer SSR |
| Seed data | `app/domain/sites.py`, `app/data/cities.json` | Five OAH cities only |
| Runtime DB | `data/confirmgate.sqlite3` | Local demo store |

**Workflow (domain):**  
`RECEIVED → FLAGGED → AWAITING_CONFIRM → CONFIRMED → FINALIZED` with `NEEDS_REVIEW` / `REJECTED` / `WITHDRAWN`. App state ≠ FHIR status. **[FACT]** `app/domain/packet.py`, `docs/DOMAIN-MODEL.md`.

**Citizen-safe fields:** foam, colour, smell, macrophytes(+non_native), riparian(+non_native), hydromorphology. Excluded: BMWP, pathogens, ARG, disease, Diptera traps, well-being, etc. **[FACT]** `app/domain/value_objects.py`.

**Media reality check:** Photo is **filename noted in provenance** (`media.noted`); bytes **not** stored; EXIF/media rules mostly null-port quiet. Phase 9 media deferred. **[FACT]** `docs/PERSISTENCE.md`, `citizen_flow.submit`, FlagEngine media ports.

**FHIR reality check:** Maps verified TemporaryOahSystem subset; colour/smell annotation-only; no FHIR Provenance resource in Bundle (IG has no Provenance profile — internal log answers HITL). **[FACT]** `docs/FHIR-SPEC.md`, `docs/REQUIREMENTS.md` Phase 5 decision.

**AI reality check:** Null default; Fake for tests; optional OpenAI; schema-validated; cannot confirm/finalize; photo AI empty. **[FACT]** `docs/AI-POLICY.md`, `app/ai/*`.

**Tests:** 196 unit/integration/HTTP tests covering domain, flags, persistence, FHIR refuse path, web phases 6–7, AI phase 8. **[FACT]**.

## 0.2 Architecture shape (as-built)

```text
web (HTTP/Jinja)
    ↓
application (citizen_flow / reviewer_flow / ObservationService)
    ↓                    ↘
domain ←—— flags (pure)   fhir (export only at FINALIZED)
    ↓
ports (repos, UoW, AiAssistPort, FlagEngine, Media/Duplicate ports)
    ↓
adapters: persistence/sqlite · ai null/fake/http · composition root
```

Dependency rule already enforced in docs/tests: domain does not import FastAPI/FHIR/AI/SQLite. **[FACT]** `docs/PERSISTENCE.md`, architecture tests.

## 0.3 Data assumptions & OAH boundaries (as-built)

| Assumption | Status |
|---|---|
| Five cities only | Enforced **[FACT]** |
| Protocol-lite categorical sensory/veg | Enforced allowlist **[FACT]** |
| Single-visit packet = unit of work | **[FACT]** — no time series store |
| Multi-source EO/sensor/lab feeds | **Absent** **[FACT]** |
| Official CS-app API ingest | **Absent / UNKNOWN** access |
| Full IG validator green | Explicitly **not claimed** **[FACT]** |
| Auth | Not implemented; demo reviewer actor **[FACT]** |

OAH ecosystem owns collect/explore/DSS/EO surfaces (CS app, Resilience Map, GEOSSIP, DipteraCAST). ConfirmGate owns **per-observation integrity → finalize FHIR**. **[FACT]** ConfirmGate spike + PRD.

## 0.4 ConfirmGate module classification (for any AquaSignal pivot)

| Module / asset | Classification | Rationale |
|---|---|---|
| `app/domain` (`ObservationPacket`, state machine, VOs, cities, sites) | **REUSE AS-IS** (as integrity subsystem) | Core HITL aggregate remains valid for citizen evidence validation |
| `app/flags` + FlagEngine rules | **REUSE AS-IS** | Packet fitness ≠ site investigation signals; keep separate |
| `app/application` citizen/reviewer flows + ports | **REUSE WITH ADAPTATION** | Keep packet lifecycle; add case/signal application services beside, not inside, packet mutators |
| `app/persistence` SQLite + UoW + provenance repo | **REUSE WITH ADAPTATION** | New tables for signals/cases/runs; same UoW pattern |
| `app/provenance` / HITL audit | **REUSE WITH ADAPTATION** | Extend action vocabulary; do not replace append-only model |
| `app/fhir` exporter/mapper/guard/registry | **REUSE AS-IS** | Still finalize-only after human authority on **observations**; cases do not auto-FHIR |
| `app/ai` AiAssistPort + Null/Fake/validate | **REUSE WITH ADAPTATION** | New optional InvestigationCopilot port mirroring same null/schema/HITL rules |
| `app/web` citizen + reviewer templates | **REUSE WITH ADAPTATION** | Keep ConfirmGate paths; add thin investigation surface later — do not rewrite into dashboard |
| `app/composition.py` | **REUSE WITH ADAPTATION** | Wire new engines only after approval |
| `docs/CONFIRMGATE-*`, HITL/AI/FHIR/FLAG specs | **REUSE AS-IS** | Remain authority for integrity path |
| `docs/WIN-PLAN.md`, StreamWitness thesis remnants | **DEPRECATE** | Already superseded; do not revive |
| `docs/PRODUCT-VALIDATION.md`, `RESEARCH-HACKATHON-OPPORTUNITY.md` | **DEPRECATE** as product authority | Historical research only |
| In-memory scaffold patterns / preliminary FHIR | **DELETE** (already gone) | Kill criteria still apply |
| Composite trust score / photo→BMWP / blockchain | **DELETE / NEVER INTRODUCE** | ConfirmGate + AquaSignal both forbid |
| Full media/EXIF pipeline | **MOVE** to post-hackathon / Phase 9 | Not required for AquaSignal-lite if fixtures carry evidence refs |
| Graph DB | **DEPRECATE** for hackathon | Relational + explicit relation rows sufficient **[INFERENCE]** |
| Resilience Map / GEOSSIP / CS CRUD clones | **DELETE from scope** | Ecosystem conflict |

---

# Hostile challenge — is AquaSignal the right pivot?

### Challenge 1 — Thesis width vs calendar

Proposed AquaSignal: continuous multi-source temporal+spatial investigation platform. ConfirmGate already consumed most of the engineering week (Phases 1–8, 196 tests). **[FACT]** Remaining calendar ≈ 7 days including deploy, Devpost, 3–5 min video. **[INFERENCE]** Full AquaSignal is a multi-sprint product; shipping it honestly by 29 Sep is near-impossible.

### Challenge 2 — Data starvation

Signal detectors (rolling baseline, MAD/IQR, EWMA, change-point) require **ordered observations over time** (and ideally multi-source). ConfirmGate stores **single-visit packets** with no time-series table. **[FACT]** schema `001_initial.sql`. Without real feeds or carefully labelled synthetic fixtures, “continuously turns fragmented observations into signals” is **demo fiction**.

### Challenge 3 — Track alignment

ConfirmGate maps cleanly to Track 3 (validation + HITL) and FHIR finalize. **[FACT]** PRD. AquaSignal drifts toward environmental intelligence / early warning — closer to explore/DSS/EO territory already occupied by Resilience Map / GEOSSIP. **[INFERENCE]** Judges may ask: “Isn’t this a thin map/analytics clone?” Impact 30% requires One Health honesty without disease detection.

### Challenge 4 — The 5–10% ConfirmGate claim is false for hackathon reality

If AquaSignal is the hero and ConfirmGate is 5–10%, you must rebuild most of the demo around signals/cases/data. In 7 days, the **working** system will still be ConfirmGate-majority. Claiming 5–10% is rhetorical. Honest ratio for a narrowed ship: ConfirmGate **~40–60%** of demo surface; Signal/Investigation **~40–60%** of *new* story — not 5–10%. **[INFERENCE]**

### Challenge 5 — 30-second clarity

ConfirmGate pitch is crisp: noisy citizen report → flags → human confirm → final FHIR. AquaSignal pitch (“something may be changing; investigate”) is scientifically safer than pollution detectors but **weaker as a hackathon hook** unless the demo shows a concrete corroboration/contradiction story on real-shaped fixtures. **[INFERENCE]**

### Challenge 6 — Scientific overclaim risk

Any detector that looks like pollution/disease/pathogen scoring fails ConfirmGate kill criteria and OAH scientific scrutiny. **[FACT]** spike kill list. AquaSignal must stay at **evidence change / inconsistency / insufficient corroboration** — not cause attribution.

### Better product if full AquaSignal fails the calendar test

**Recommended narrowed core (name optional):**  
**Site Investigation Brief** — given multiple **human-authorized** observations at one seeded site (plus 1 fixture external series), emit explainable **corroboration / contradiction / insufficiency** relations and open a minimal `InvestigationCase`, with reproducible `AnalysisRun`. ConfirmGate remains the gate for citizen evidence. Branding can be “AquaSignal” only if messaging matches this narrowed core.

---

# A. PRODUCT VERDICT

## **BUILD WITH CHANGES**

**Not** BUILD full continuous multi-source AquaSignal.  
**Not** abandon ConfirmGate.  
**Not** PIVOT AGAIN to vision-scoring / trust-score / map clone.

### Why BUILD WITH CHANGES

1. **Direction is right:** Track 3 integrity alone is narrow for Impact 30%; investigation/corroboration across observations is a defensible One Health *use* of confirmed evidence. **[INFERENCE]**  
2. **Full thesis is wrong for this deadline:** continuous multi-source + graph + rich case lifecycle + EO APIs exceeds solo 7-day feasibility without theater. **[INFERENCE]**  
3. **ConfirmGate is an asset, not ballast:** state machine, FlagEngine, provenance, finalize FHIR are rare clone-resistant depth. Shrinking it to 5–10% wastes technical 20% and Track 3 fit. **[FACT]**+**[INFERENCE]**  
4. **Changes required:** (a) cut AquaSignal to Site Investigation Brief; (b) fixture-first data strategy; (c) ≤3 deterministic detectors; (d) FHIR still only after human finalize of observations; (e) keep Null AI; (f) no maps/dashboards/pollution scores.

### Kill / refuse conditions for AquaSignal work

Refuse to implement / submit if the pivot:

1. Claims pollution, pathogen, disease, outbreak, or water-safety detection.  
2. Emits OAH FHIR from unconfirmed packets or from AI case conclusions.  
3. Introduces a composite trust/risk score.  
4. Requires live proprietary APIs that cannot be demonstrated offline.  
5. Rebuilds Resilience Map / GEOSSIP / CS app as the hero.  
6. Makes AI required for the core demo.  
7. Invents hydrology flow direction or unverified TemporaryOahSystem codes.

---

# B. CORE PRODUCT THESIS

**One paragraph (narrowed):**  
AquaSignal (hackathon scope) turns **multiple human-authorized urban stream observations**—and a small set of **labelled fixture series**—into **explainable investigation signals** at a seeded OneAquaHealth site by running **versioned deterministic detectors** for temporal change, local contradiction, and insufficiency, assembling an **evidence brief** (supports / conflicts / missing) inside a minimal `InvestigationCase`, while **ConfirmGate** remains the integrity gate for each citizen observation and **FHIR export stays finalize-only after human authority**—never as pollution diagnosis, never as AI conclusion, never as a Resilience Map clone.

**Questions answered (hackathon):**  
1. Might something be changing at this site *in the evidence we have*?  
2. Is there enough corroboration to open/continue an investigation?  
3. What supports, conflicts, or is missing?  
4. Can a reviewer reproduce the analysis run?

**Questions explicitly not answered:** cause, pollution load, pathogen presence, disease risk, hydrologic routing, policy action.

---

# C. 5–10% CONFIRMGATE BOUNDARY — CORRECTED

### Rejected claim

“ConfirmGate becomes ~5–10% subsystem” for this hackathon. **[INFERENCE]** That ratio fits a post-hackathon platform vision, not a 7-day ship.

### Corrected boundary

| Concern | Owner | Notes |
|---|---|---|
| Single-visit protocol-lite ingest | ConfirmGate | Unchanged |
| Packet FlagEngine (completeness, vocab, nonclaim, geo, duplicate, FHIR readiness) | ConfirmGate | Unchanged; **not** the Signal Engine |
| Human confirm / reviewer accept / reject | ConfirmGate | Authority for observation fields |
| Finalize + FHIR Bundle | ConfirmGate / `app/fhir` | Still only after `FINALIZED` |
| Append-only packet provenance | ConfirmGate | Extended with case/run events later |
| Cross-observation detectors | **AquaSignal-lite** | New; consumes **FINALIZED** (or fixture) evidence only for investigation inputs **[INFERENCE]** recommended policy |
| InvestigationCase lifecycle | AquaSignal-lite | New; human closes conclusions |
| AnalysisRun reproducibility | AquaSignal-lite | New |
| Optional Investigation Copilot | AquaSignal-lite AI port | Null works; schema-validated; never opens/closes case alone |

**Demo surface target (honest):** ConfirmGate path still visible (~half the 2–3 min video); investigation brief is the *new* differentiator (~half). Subsystem LOC may grow toward signals, but ConfirmGate remains first-class, not a footnote.

**Input gate policy (recommended):** Investigation detectors may **read** only:

- `ObservationPacket` in `FINALIZED` (human-authorized), and/or  
- Explicitly labelled fixture `Evidence` rows (synthetic/demo), and/or  
- Optional imported public series marked `source_class=fixture|public`.

Do **not** feed `RECEIVED`/`FLAGGED` drafts into signals (launders unconfirmed noise into “intelligence”). **[INFERENCE]**

---

# D. DOMAIN MODEL

Smallest correct set for narrowed AquaSignal. Do not copy enterprise case-management blindly.

### Aggregates

| Aggregate | Purpose | Lifecycle (minimal) |
|---|---|---|
| **`ObservationPacket`** (existing) | Citizen visit integrity | ConfirmGate states unchanged |
| **`InvestigationCase`** | Human-owned investigation container for one `SiteRef` (+ optional window) | See §G/§N — not DETECTED→… cargo-cult |
| **`AnalysisRun`** | Immutable record of one detector suite execution | `STARTED → SUCCEEDED \| FAILED` |

### Entities

| Entity | Purpose |
|---|---|
| **`EvidenceItem`** | Normalized pointer to an observation, fixture row, or media note used in analysis |
| **`EnvironmentalSignal`** | One detector output instance (typed, versioned, explainable) |
| **`EvidenceRelation`** | Explicit supports / conflicts / duplicates / insufficient_link between evidence items or evidence↔signal |
| **`HumanDecision`** | Case-level decision (open, note, dismiss, request_more_evidence, conclude_insufficient, conclude_change_suspected) with reason codes |

### Value objects

| VO | Purpose |
|---|---|
| `SiteRef` | Reuse ConfirmGate seed |
| `TimeWindow` | `[start, end)` for run/case |
| `DetectorId` + `DetectorVersion` | Reproducibility |
| `SignalType` | e.g. `temporal_shift`, `frequency_burst`, `cross_source_conflict`, `insufficient_evidence` — **not** pollution/disease types |
| `RelationType` | `supports`, `conflicts`, `duplicates`, `insufficient` |
| `GeoCell` / `NeighborhoodSpec` | Simple radius or same-`site_ref_id` — **no** flow direction |
| `EvidenceSnapshotRef` | Hash + pointer to frozen input set for a run |
| `Actor` | Reuse ConfirmGate actor types (+ `system` for detectors) |

### Explicit non-entities

- `TrustScore`, `RiskIndex`, `PollutionLevel`, `PathogenAlert`  
- `HydrologicEdge` / directed river graph (do not invent)  
- Graph-DB native nodes as persistence requirement

### Invariants (product-level)

1. Signals are **hypothesis aids**, not environmental truth.  
2. Case conclusions require **HumanDecision**.  
3. AI cannot create authoritative `HumanDecision` or finalize FHIR.  
4. Detector versions + input snapshot hash required for any displayed signal.  
5. No composite score field anywhere in the model.

---

# E. ARCHITECTURE

Keep **modular monolith**. Do not microservice. Do not add a graph DB.

### Proposed package layout (design only — not copy-blind)

```text
app/
  domain/           # ConfirmGate packet + NEW case/signal VOs (or app/domain_signal/ if split preferred)
  flags/            # packet FlagEngine ONLY
  signals/          # NEW: detectors + SignalEngine orchestration (pure)
  application/      # existing flows + InvestigationService / AnalysisService
  persistence/      # existing + new tables/repos
  fhir/             # unchanged boundary
  ai/               # existing + optional InvestigationCopilotPort
  provenance/       # shared append-only semantics
  web/              # existing + later thin /investigate routes
  composition.py
  main.py
```

**Prefer** `app/signals/` separate from `app/flags/` — different questions (packet fitness vs cross-evidence change). **[INFERENCE]**

### Dependency direction

```text
web → application → domain
                 ↘ signals (pure functions on snapshots)
                 ↘ flags (packet only)
application → ports ← adapters (sqlite, ai, clock, fixture loader)
fhir ← application (export packet only)
signals must NOT import web/fhir/ai SDKs/sqlite
```

### Pipeline (conceptual)

```text
Evidence sources
  → EvidenceSnapshot (frozen, hashed)
  → SignalEngine(detectors[])
  → EnvironmentalSignal[] + EvidenceRelation[]
  → (optional) open/update InvestigationCase
  → HumanDecision
  → (optional) Investigation Copilot narrative — advisory only
  → Provenance events for run + decisions
```

### Persistence recommendation

**Relational SQLite** (extend current DB) with tables for evidence_items, signals, relations, cases, analysis_runs, evidence_snapshots. Store relations as explicit rows (`from_id`, `to_id`, `type`, `run_id`). Promote to Postgres post-hackathon if needed. Graph DB: **out of scope**.

---

# F. DATA CONTRACTS (conceptual — no implementation)

### Observation (ConfirmGate-aligned)

Logical: identity, site, effective time, field map, workflow state, confirmation hash, flag snapshot, optional media refs. Authoritative for investigation **only when FINALIZED** (recommended).

### Evidence

| Field (conceptual) | Notes |
|---|---|
| `evidence_id` | Opaque |
| `source_class` | `confirmgate_packet` \| `fixture` \| `public_series` |
| `site_ref_id` | Required |
| `observed_at` | Required for temporal detectors |
| `payload_ref` | Packet id or fixture row id |
| `content_hash` | For snapshotting |
| `license_tag` | Required for non-owned data **[VERIFY]** |

### EnvironmentalSignal

| Field | Notes |
|---|---|
| `signal_id` | Opaque |
| `detector_id` / `detector_version` | Required |
| `signal_type` | Closed enum (non-diagnostic) |
| `site_ref_id` | Required |
| `window` | TimeWindow |
| `summary` | Human-readable, non-causal |
| `metrics` | Structured extras (delta, n, threshold) — **not** a trust score |
| `evidence_ids` | Inputs cited |
| `analysis_run_id` | Required |
| `explain_payload` | Deterministic explanation structure |

### EvidenceRelation

`relation_id`, `run_id`, `type` ∈ {supports, conflicts, duplicates, insufficient}, `left_ref`, `right_ref`, `rationale_code`, `message`.

### InvestigationCase

`case_id`, `site_ref_id`, `state`, `opened_at`, `window`, `signal_ids[]`, `decision_ids[]`, `reproducibility_refs[]`.

### AnalysisRun

`run_id`, `started_at`, `finished_at`, `status`, `detector_set_version`, `snapshot_hash`, `params_hash`, `signals_produced`, `error` if failed.

### EvidenceSnapshot

`snapshot_id`, `hash`, `created_at`, `evidence_id list` (ordered), `source manifest`.

### HumanDecision

`decision_id`, `case_id`, `actor`, `at`, `decision_code`, `rationale`, `linked_signal_ids`.

---

# G. SIGNAL ENGINE DESIGN

**Principle:** Deterministic, versioned, explainable, testable. No ML required for MVP. No pollution/disease labels.

**Orchestrator:** `SignalEngine.evaluate(snapshot, params) → {signals, relations}` pure w.r.t. inputs (clock injected via snapshot times).

### Detector catalog (hackathon-rational subset)

Ship **at most three** for MVP (mark others deferred).

---

### G1. `temporal_baseline_shift` (PRIORITY — ship)

| Aspect | Design |
|---|---|
| **Method** | For one ordinal/categorical-mapped series at one site: rolling window baseline (median) + robust scale (MAD or IQR); flag when latest point or short recent window exceeds k·scale from baseline |
| **Input** | Ordered `(t, value)` for one variable (e.g. foam mapped absent=0, present=1, extensive/abundant=2); `n_min`, `window`, `k` |
| **Output** | `signal_type=temporal_shift` + metrics `{baseline, recent, delta, mad, k, n}` + evidence ids |
| **Assumptions** | Values comparable over time; mapping of categories is documented; irregular sampling tolerated but reduces power |
| **Limits** | Categorical→ordinal is lossy; seasonality not modelled; small n → high false pos/neg |
| **Complexity** | O(n) per series |
| **Data needs** | ≥ `n_min` (recommend 8–12) points — **fixtures required** **[INFERENCE]** |
| **Failure** | If n < n_min → emit `insufficient_evidence` relation/signal, not a shift |
| **Explainability** | “Recent foam ordinal mean X vs baseline median Y (MAD=Z); threshold k=…” |
| **Testability** | Golden series: flat / step-up / noisy / sparse |
| **Versioning** | `temporal_baseline_shift@0.1.0` + param hash |

---

### G2. `cross_observation_contradiction` (PRIORITY — ship)

| Aspect | Design |
|---|---|
| **Method** | Same site, overlapping time window: compare FINALIZED packets (or fixtures) on shared codes; if values disagree beyond allowed equivalence set → `conflicts`; if agree → `supports`; near-duplicate submissions → `duplicates` (reuse ConfirmGate duplicate intuition at case level) |
| **Input** | ≥2 evidence items; field code allowlist; equivalence tables |
| **Output** | `EvidenceRelation`s (+ optional signal `cross_source_conflict` when ≥1 hard conflict) |
| **Assumptions** | Same site_ref means comparable locus (city-level seed sites are coarse — disclose) **[FACT]** sites are city centroids |
| **Limits** | City-level sites make “contradiction” weak geographically; treat as **protocol contradiction**, not spatial truth |
| **Complexity** | O(m²) on evidence count (m small) |
| **Data needs** | Multiple packets/fixtures per site — seed in demo |
| **Failure** | One evidence only → insufficient |
| **Explainability** | Field-level diff table |
| **Testability** | Pair fixtures agree/disagree/duplicate |
| **Versioning** | `cross_observation_contradiction@0.1.0` |

---

### G3. `frequency_burst` (OPTIONAL — ship only if time)

| Aspect | Design |
|---|---|
| **Method** | Count submissions per site in sliding time window; compare to baseline rate (mean+k·σ or Poisson upper) |
| **Input** | Event times only |
| **Output** | `frequency_burst` or insufficient |
| **Assumptions** | Reporting process somewhat stable (often false in CS) |
| **Limits** | Confounds campaigns/hackathon demos; easy to misread as environmental change |
| **Complexity** | O(n) |
| **Data needs** | Many timestamps — may be synthetic |
| **Failure** | Sparse → insufficient |
| **Explainability** | “N reports in W days vs baseline μ” |
| **Testability** | Inject burst series |
| **Versioning** | `frequency_burst@0.1.0` |
| **Hackathon note** | High misinterpretation risk — **default DEFER** unless demo narrative is explicitly “reporting surge, not pollution.” |

---

### G4. Deferred detectors (design recorded, do not implement now)

| Detector | Sketch | Why defer |
|---|---|---|
| EWMA shift | Exponentially weighted mean breach | Overlaps G1; extra params |
| Change-point (PELT/binary segmentation) | Offline change-point on series | Easy to overclaim; heavier deps |
| Spatial neighborhood consensus | Compare site to kNN sites in radius | Only 5 city seeds — neighborhood is fake **[FACT]** |
| Hydrologic upstream/downstream | Directed network | **Do not invent** |
| Multi-source EO NDVI/water index fusion | Satellite features | GEOSSIP overlap + API/time **[INFERENCE]** |

### Corroboration model (NOT a trust score)

Render four **counts / lists**, never a 0–100:

- Supports  
- Conflicts  
- Duplicates  
- Insufficient / missing (expected sources not present)

Optional label: `evidence_stance` ∈ {`corroborated`, `contested`, `insufficient`, `single_source`} derived by **transparent rules** (e.g. contested if conflicts≥1; insufficient if n<n_min; else corroborated if supports≥1). Disclose rule text in UI. **Not** a score.

---

# H. DATA SOURCE PLAN

Honesty rule: **no invented live APIs**. Prefer fixtures.

| Source | Class | Feasibility by 29 Sep | License / access | Role |
|---|---|---|---|
| ConfirmGate FINALIZED packets | Real (app-generated) | **Yes** **[FACT]** | Owned | Primary citizen evidence |
| Hand-authored JSON/CSV fixture series (Coimbra foam/colour ordinal) | Synthetic labelled | **Yes** | Owned MIT | Enable temporal detector demo |
| OAH factsheets / protocols | Reference docs | Yes (PDF) | Cite Zenodo DOIs **[FACT]** URLs in AGENTS | Vocabulary / non-claim language — not time series |
| OAH FHIR IG TemporaryOahSystem | Real terminology | Yes (CI build) | HL7 IG terms **[VERIFY]** redistrib | Mapping only via existing FHIR adapter |
| CS app observations | Real platform | **Unknown / blocked** without API **[UNKNOWN]** | Login wall | Do **not** scrape; out unless official export |
| Resilience Map / GEOSSIP layers | Real EO/explore | Integration heavy **[INFERENCE]** | Unknown TOS **[VERIFY]** | Out of MVP — cite as complementary, do not clone |
| Public WQ portals (EEA, national) | Real | Possible but city alignment + licenses **[VERIFY]** | Per-portal | Optional post-hackathon; not required for demo |
| Sensor IoT streams | Real/synth | No time | — | Out |

**Demo data strategy (mandatory if signals ship):**

1. Seed 1 site (Coimbra) with **labelled** fixture timeline (shift + flat controls).  
2. Seed 2–3 FINALIZED packets (agree + conflict pair).  
3. Mark all synthetic rows `source_class=fixture` in UI.  
4. Never present fixtures as live OAH production data.

---

# I. OAH BOUNDARY

| Capability | OAH today | AquaSignal-lite owns | ConfirmGate owns |
|---|---|---|---|
| Citizen capture mobile UX | CS app | No | Protocol-lite web subset only |
| Explore / resilience mapping | Resilience Map | No | No |
| EO browsing | GEOSSIP | No | No |
| Lab / mosquito models | Factsheets / DipteraCAST | No | No |
| FHIR IG profiles | hl7-eu/oah | Consume via mapper | Export Bundle after finalize |
| Observation integrity HITL | Gap ConfirmGate fills | Consumes outputs | **Owns** |
| Cross-observation investigation brief | **Gap** (proposed) | **Owns (narrow)** | Supplies authorized evidence |
| Decision support / policy | DSS (ecosystem) | Does not replace | One Health sentence template only |

**Integration posture:** Extend OAH quality→investigation path; feed cleaner authorized observations; do not replace hubs. FHIR remains **observation export**, not “case FHIR” unless IG later defines it (**[UNKNOWN]** / out of scope).

---

# J. AI BOUNDARY

Mirror ConfirmGate Phase 8 discipline (`docs/AI-POLICY.md`).

| Allowed | Forbidden |
|---|---|
| Summarize existing signals/relations in plain language | Decide case outcome |
| Suggest which missing evidence types to collect (from closed list) | Pollution/pathogen/disease claims |
| Explain detector math already computed | Alter metrics/severity |
| NullInvestigationCopilot always works | AI required for demo |
| Schema-validated structured advisory | Free-form FHIR / TemporaryOahSystem invention |
| Provenance of model/prompt versions | Writing DB/case state directly |

Port sketch: `InvestigationCopilotPort.explain_case(case, run) → AdvisoryBrief` with validation + Null implementation.

---

# K. REPRODUCIBILITY MODEL

| Mechanism | Role |
|---|---|
| `EvidenceSnapshot` + content hash | Freeze inputs |
| `AnalysisRun` params hash | Freeze detector config |
| `detector_set_version` | Code/rules identity |
| Append-only provenance actions | `analysis.started`, `analysis.completed`, `signal.emitted`, `case.decision`, … |
| Golden fixture tests | Bit-stable signals for fixed snapshot |
| Display “Re-run” | Recompute; if code changed, version bump — do not silently rewrite old run |

**Non-goal:** Blockchain hash chains (ConfirmGate already skipped; keep skipped). **[FACT]** `docs/PERSISTENCE.md`.

---

# L. PERFORMANCE / SCALABILITY MODEL

Hackathon scale: 5 sites, dozens–hundreds of evidence rows, interactive single-process SQLite. **[INFERENCE]**

| Concern | Stance |
|---|---|
| Detector CPU | Trivial at demo n |
| Concurrent writers | Existing optimistic `revision` on packets; cases can use same pattern |
| Fan-out multi-city EO | Out of scope |
| Post-hackathon | Batch runs via queue; Postgres; still monolith until proven need |

Do not design Kubernetes, stream processing, or near-real-time alerting for MVP.

---

# M. SECURITY / PRIVACY IMPACT

| Topic | Impact of pivot |
|---|---|
| Auth still absent | Investigation desk must disclose demo-open access like `/review` **[FACT]** HITL-POLICY |
| PII | Keep opaque ids; avoid storing raw photos until EXIF scrub exists |
| AI | Same as Phase 8 — no keys in git; no photo bytes to providers in MVP |
| Fixture mislabeling | Integrity risk if synthetic presented as live — UI must label |
| Scraping CS/GEOSSIP | Forbidden without permission |
| Export | FHIR still gated; case conclusions must not appear as Observation values without human finalize path |

---

# N. PHASED IMPLEMENTATION PLAN

**Global rule:** Do not start a phase until human approves this spike and the previous phase exit criteria. Prefer shippable slices over platform completeness.

### Engineering principles (future phases must follow)

1. Understand invariants before coding (HITL, finalize-only FHIR, no trust score, no disease claims).  
2. Inspect current modules/tests before editing.  
3. Name packages touched; keep dependency direction.  
4. Smallest design; fixture-first.  
5. Write acceptance tests with the change.  
6. Null AI path always green.  
7. Hostile self-check against kill criteria.  
8. No scope expansion without explicit human approval.  
9. No secrets in git.

---

### Phase A0 — Decision freeze (docs only) — **THIS DOCUMENT**

| | |
|---|---|
| **Objective** | Accept BUILD WITH CHANGES + narrowed thesis |
| **Modules** | `docs/AQUASIGNAL-ARCHITECTURE-SPIKE.md` only |
| **Prerequisites** | ConfirmGate Phases 1–8 green |
| **Tests** | N/A |
| **Acceptance** | Human selects: (1) narrowed AquaSignal, (2) ConfirmGate-only polish, or (3) stop |
| **Non-goals** | Any code |

---

### Phase A1 — Domain + contracts for Case/Run/Signal (no UI)

| | |
|---|---|
| **Objective** | Types + invariants + illegal transitions for `InvestigationCase` / `AnalysisRun` |
| **Modules** | `app/domain` (or `app/signals/domain`), tests |
| **Prerequisites** | A0 approval |
| **Tests** | State/invariant unit tests |
| **Acceptance** | Case cannot “auto-conclude”; runs immutable after success |
| **Non-goals** | Detectors, UI, FHIR changes |

**Minimal case lifecycle (recommended):**  
`OPEN → UNDER_REVIEW → CLOSED` with `DISMISSED` as alternate close.  
Signals may exist **without** a case (run-only). Opening a case is a human or explicit system suggestion **acknowledged by human**. Avoid long DETECTED→TRIAGED→… chains.

---

### Phase A2 — Persistence for snapshots/runs/signals/relations

| | |
|---|---|
| **Objective** | SQLite tables + repos + UoW integration |
| **Modules** | `app/persistence`, migrations `002_*.sql` |
| **Prerequisites** | A1 |
| **Tests** | Repo + transaction tests |
| **Acceptance** | Round-trip run + signals; append-only provenance events |
| **Non-goals** | HTTP routes |

---

### Phase A3 — SignalEngine with G1 + G2 only + fixtures

| | |
|---|---|
| **Objective** | Deterministic detectors + labelled Coimbra fixtures |
| **Modules** | `app/signals`, `tests/fixtures/signals/` |
| **Prerequisites** | A2 |
| **Tests** | Golden vector tests for shift/conflict/insufficient |
| **Acceptance** | Same snapshot → same signals; fixture labels present |
| **Non-goals** | EWMA, change-point, spatial, frequency_burst, AI, maps |

---

### Phase A4 — Application InvestigationService + ConfirmGate read gate

| | |
|---|---|
| **Objective** | Build snapshot from FINALIZED packets + fixtures; run engine; open case with HumanDecision |
| **Modules** | `app/application` |
| **Prerequisites** | A3 |
| **Tests** | Flow tests; refuse draft packets as evidence **[INFERENCE]** policy |
| **Acceptance** | End-to-end in-process demo without browser polish |
| **Non-goals** | Copilot, dashboard KPIs |

---

### Phase A5 — Thin web surface + 2–3 min demo narrative

| | |
|---|---|
| **Objective** | One investigation page: evidence stance lists, signal explanations, re-run meta, link back to ConfirmGate packet |
| **Modules** | `app/web`, templates |
| **Prerequisites** | A4; deploy path exists |
| **Tests** | HTTP smoke |
| **Acceptance** | Video can show: conflict pair → temporal fixture shift → human decision → provenance/repro hash; plus ConfirmGate finalize FHIR beat |
| **Non-goals** | Map, charts extravaganza, auth, multi-tenant |

---

### Phase A6 — Optional Investigation Copilot (Null-first)

| | |
|---|---|
| **Objective** | Advisory narrative only |
| **Modules** | `app/ai` extension |
| **Prerequisites** | A5; time remaining |
| **Tests** | Null + schema reject + no authority |
| **Acceptance** | Demo works with AI off |
| **Non-goals** | Photo ecology, auto-close cases |

---

### Explicitly NOT now (user brief + this spike)

- AquaSignal full platform / continuous multi-source production system  
- Pollution/disease/pathogen detectors  
- Trust/risk scores  
- Graph DB  
- Hydrologic directionality  
- Resilience Map / GEOSSIP / CS CRUD clone  
- Chatbot-first UX  
- AI WQ predictor  
- Rewriting ConfirmGate core  
- Dashboards as the product  
- Invented datasets presented as live official OAH feeds  
- PoC notebooks as submission  

---

# O. RISK REGISTER

| ID | Category | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|---|
| R1 | Hackathon delivery | Over-scope AquaSignal; ship nothing polished | **High** | **Critical** | BUILD WITH CHANGES; Phases A1–A5 only; cut A6 |
| R2 | Data | No real time series → theater | **High** | **High** | Labelled fixtures + disclose; FINALIZED packets for contradiction |
| R3 | Scientific | Judges read signals as pollution alerts | **Medium** | **Critical** | Copy discipline; non-claim gates; kill criteria |
| R4 | Product | ConfirmGate pitch diluted; neither story lands | **Medium** | **High** | Split video beats; keep FHIR finalize |
| R5 | Technical | Domain tangle (flags vs signals) | **Medium** | **Medium** | Separate `app/signals`; no FlagEngine misuse |
| R6 | Integration | Temptation to scrape CS/GEOSSIP | **Medium** | **High** | Fixture-only + cite hubs as complementary |
| R7 | FHIR | Case conclusions leaked into Observation | **Low** | **High** | FHIR path untouched except packet finalize |
| R8 | AI | Copilot overclaim | **Medium** | **High** | Null-first; schema; subordinate |
| R9 | Spatial | City centroid sites make “spatial” meaningless | **High** | **Medium** | Same-site only; no fake neighborhoods |
| R11 | Docs lag | README still “Phase 1” confuses judges/agents | **High** | **Low** | Update README after product decision |
| R12 | Media | Photo evidence still filename-only | **High** | **Low–Med** | Don’t block signals on media pipeline |

---

# P. FINAL RECOMMENDATION

### Honest hackathon feasibility

| Option | Feasibility by 29 Sep | Differentiated? | Track fit | Recommend? |
|---|---|---|---|---|
| Full AquaSignal (continuous multi-source intelligence) | **Poor** | High on paper, fake in practice without data | Fuzzy vs hubs | **No** |
| ConfirmGate-only polish + deploy + video | **Good** | Moderate (integrity+FHIR) | Strong Track 3 | **Safe backup** |
| **Narrowed AquaSignal = Site Investigation Brief on ConfirmGate** | **Fair–Good** if ruthlessly cut | **Yes** if contradiction+temporal fixture+repro shown | Track 3 + Impact story | **Yes — preferred if energy remains** |
| Vision/trust-score/map clone | — | — | Kill | **No** |

### Smaller differentiated core (canonical)

**Name for engineering:** Site Investigation Brief (brand “AquaSignal” only if messaging matches).  
**Must ship beats:**

1. ConfirmGate: flag → confirm → finalize → FHIR `final` Bundle.  
2. Two authorized observations conflict at Coimbra → `conflicts` relation explained.  
3. Fixture temporal shift → `temporal_shift` signal with baseline/MAD explanation + insufficient path on sparse series.  
4. `AnalysisRun` hash shown; human records a non-diagnostic decision.  
5. Null AI path; no trust score; no disease language.

### What to tell yourself daily

Calendar is the hard constraint. Every hour on maps, EO APIs, or extra detectors is an hour not spent on deploy and video.

### Authority note

Until human approval of this spike:

- ConfirmGate docs remain implementation authority for existing code.  
- This document is the **candidate** authority for any AquaSignal-lite work.  
- **Do not implement AquaSignal.**

---

## ConfirmGate → AquaSignal module classification (summary table)

| Classification | Items |
|---|---|
| **REUSE AS-IS** | Packet domain core, FlagEngine, FHIR exporter/guard/registry, city/site seed, HITL packet policies, Null AI pattern |
| **REUSE WITH ADAPTATION** | Application services, persistence/UoW, provenance actions, web shell, composition, AI port family |
| **MOVE** | Full media/EXIF (to later); any future Postgres |
| **DEPRECATE** | WIN-PLAN/StreamWitness thesis; research docs as authority; graph DB idea; 5–10% ConfirmGate rhetoric |
| **DELETE / NEVER** | Trust scores; preliminary FHIR; photo→BMWP/pathogen; hub clones; hydrology invention |

---

## Demo thesis (2–3 min — backend mechanics, not polish)

1. **Integrity (45–60s):** Submit incomplete → hard flags; fix → confirm → finalize → show FHIR `status=final` + refuse path mention.  
2. **Investigation (60–90s):** Open Coimbra brief → show conflict between two finalized packets → run analysis on fixture series → show temporal shift metrics + insufficient control → human decision “request more evidence” / “change suspected in evidence only.”  
3. **Reproducibility (20–30s):** Show run id, snapshot hash, detector version; provenance list.  
Close: “We don’t detect pollution—we detect when evidence deserves investigation, with humans in control.”

---

## Global reminder for future agents

Phases must follow: understand → inspect → modules → smallest approach → risks → acceptance → implement → tests → run → hostile review → docs if behavior changes → propose next phase only. No AquaSignal implementation without human decision on this spike.

---

# FINAL DECISION LINE

**Verdict: BUILD WITH CHANGES** — narrowed Site Investigation Brief atop ConfirmGate; reject full continuous AquaSignal for this deadline.

**AWAITING HUMAN DECISION — DO NOT IMPLEMENT AQUASIGNAL**
