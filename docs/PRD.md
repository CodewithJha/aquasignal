# ConfirmGate — Product Requirements Document (PRD)

Status: DRAFT  
Version: 0.1  
Date: 21 Sep 2026  
Owner: ConfirmGate  
Source of truth: CONFIRMGATE-ARCHITECTURE-SPIKE.md  

**Legend:** Claims without a primary citation are marked **[INFERENCE]**, open facts **[UNKNOWN]**, and IG/protocol items needing code/value-set confirmation **[VERIFY]**. Do not treat this PRD as authority over the architecture spike.

---

## 1. Product identity

| Field | Definition |
|---|---|
| **Name** | ConfirmGate |
| **One-sentence thesis** | ConfirmGate makes protocol-lite citizen stream observations usable for OneAquaHealth by applying explainable quality flags, requiring human confirmation, and emitting IG-conformant FHIR `Location`/`Observation` only after authority—never by AI auto-scoring. |
| **Short description** | A Track 3 observation-integrity lifecycle: citizen submits Annex I–ish fields + photo evidence for one of five OAH cities → deterministic FlagEngine raises structured quality flags (no trust score) → optional AI suggestions → human must confirm or edit → optional reviewer → only then export IG-shaped FHIR Bundle + Provenance + one cited, non-diagnostic One Health sentence. |
| **Hackathon track** | Primarily **Track 3 — AI-Supported Assessment** (validation + HITL). FHIR finalize also speaks to **Track 7 — Digital Health Standards** without making ConfirmGate a FHIR server. **[FACT]** Devpost track list via spike / research. |
| **OAH ecosystem relationship** | **Extends** the citizen-science quality path toward hub tools (CS app, Resilience Map, DSS, DipteraCAST, GEOSSIP). Does **not** replace those products. Feeds cleaner, human-authorized observations; does not rebuild capture apps, maps, DSS engines, or mosquito prediction AI. |

**Supersedes:** StreamWitness “factsheet checklist” / photo→stream-health thesis in older `WIN-PLAN.md` / research framing. Those docs remain historical context only.

---

## 2. Problem

**Problem statement (Track 3):** Citizen stream observations are inconsistent and error-prone, so One Health tools cannot safely treat them as decision-grade inputs. **[FACT]** Devpost Track 3 wording (via spike).

**Integrity path (what ConfirmGate solves):**

1. Protocol vocabulary is unconstrained or free-text → invents lab-grade claims.  
2. No explainable fitness signals → curators cannot defend accept/reject.  
3. App “draft” is confused with FHIR `Observation.status` → non-conformant or premature interop.  
4. AI (if present) is treated as authority → launders photo guesses into ecology.  
5. No append-only provenance → HITL cannot be audited.

**What ConfirmGate is *not* solving:** Photo → stream health / BMWP / pathogen / Diptera / disease scoring. Vision ecology is a scientific kill path, not the product core.

**Pain reality:** Strong for officers/curators who must filter CS noise; partial for citizens (feedback that a report was usable). Exact current CS-app QC process: **[UNKNOWN]** (login wall).

---

## 3. Target users

No invented polished personas. Roles only:

| Role | Relationship to product | Notes |
|---|---|---|
| **Primary — Citizen / submitting observer** | Creates and confirms own protocol-lite packet for a seeded OAH site | Must interact for ingest. May be organised volunteer or semi-trained CS participant. |
| **Secondary — Reviewer / curator** | Adjudicates flagged packets (accept / edit / reject / override with reason codes) | Secondary UX (`/review`). Whether a formal OAH reviewer role exists today: **[UNKNOWN]**. |
| **System (rules + exporter)** | Raises flags; refuses invalid export; writes provenance | Not a “user,” but holds hard gates. |
| **Out of hackathon primary UX** | Municipal officer reading a separate EvidenceBrief product | Spike: one templated One Health sentence on `/fhir` is enough for Impact language; not a second polished officer app. |

---

## 4. User jobs

AI is **not** a user job. Jobs are human (or system-gate) work:

| Job | Actor | Outcome |
|---|---|---|
| **Submit** | Citizen | Packet with city/site, protocol-lite fields, photo evidence |
| **Understand flags** | Citizen / reviewer | See structured severity + plain reasons; know block vs warn |
| **Correct** | Citizen / reviewer | Edit enums/fields and/or media until gates allow progress |
| **Confirm** | Citizen (author) | Attest field snapshot; authority for self-report values |
| **Review** | Reviewer | Queue of `NEEDS_REVIEW` / override candidates (**Phase 7**) |
| **Approve / reject / override** | Reviewer (or system hard reject) | Coded decision; overrides require reason |
| **FHIR export** | Citizen after explicit finalize | `/fhir` Bundle view/download — FINALIZED only (**Phase 6**) |

Optional AI may **suggest** categorical labels or photo-protocol notes; accepting a suggestion is still a human edit job, not an AI job.

---

## 5. Core journey

```
Submit → Validate/Flag → Correct → Optional AI → Human confirm
  → Optional reviewer → Finalize → OAH FHIR (+ cited One Health sentence)
```

### Domain workflow vs FHIR status (invariant)

| Concept | Lives where | FHIR `Observation` exists? |
|---|---|---|
| Draft / flagged / awaiting confirm / needs review / confirmed | **Domain** `ObservationPacket.workflow_state` | **No** |
| Exported Bundle | Derived `FhirExport` at finalize | **Yes** — and only then |
| FHIR `Observation.status` | Only in exported resources | Always **`final`** for OAH-profiled Observations **[FACT]** IG FSH (via spike) |

**Never** emit OAH-profiled Observations for unconfirmed packets. Prefer exporter **refusal** over invalid Bundles. App must not use `preliminary` as a stand-in for “not yet confirmed.”

### States (product meaning)

| State | Meaning | FHIR? |
|---|---|---|
| `RECEIVED` | Packet created; media/fields present or partial | No |
| `FLAGGED` | FlagEngine ran; flags recorded | No |
| `AWAITING_CONFIRM` | No standing hard reject; ready for human authority | No |
| `NEEDS_REVIEW` | Escalation to reviewer | No |
| `CONFIRMED` | Human attested field snapshot; ready to export | No (yet) |
| `FINALIZED` | Bundle written; terminal success | **Yes** |
| `REJECTED` | Hard reject or human reject; terminal | No |
| `WITHDRAWN` | Author withdrew before finalize; terminal | No |

Happy path: `RECEIVED → FLAGGED → AWAITING_CONFIRM → CONFIRMED → FINALIZED`. Branches: `NEEDS_REVIEW`, `REJECTED`, `WITHDRAWN` per architecture spike Part 5.

---

## 6. Boundaries

### ConfirmGate IS

- Observation **integrity workflow** for protocol-lite CS inputs  
- Deterministic **validation + structured quality flags** (severities; no composite score)  
- **HITL** confirm/edit as authority gate  
- Secondary **reviewer** desk for escalations  
- **Append-only provenance** answering audit questions  
- **FHIR export** of IG-shaped `Location` + `Observation`(s) **only after finalize** (internal audit Provenance; no FHIR Provenance resource until IG requires it — Phase 5)  
- One **citation-bound, non-diagnostic** One Health sentence template on finalize view  

### ConfirmGate IS NOT

- A stream-health / ecological **scorer**  
- A **pathogen**, AMR, pharmaceutical, or disease detector  
- A replacement for **DipteraCAST**, **DSS**, **CS app**, Resilience Map, or GEOSSIP  
- A free-form ecology **chatbot**  
- A full **FHIR server** (SMART auth, resource persistence API, multi-tenant EHR)  
- A **trust-score** / black-box 0–100 platform  
- Multi-agent swarm theater, blockchain ledger, or Isolation-Forest sensor demo  

---

## 7. Supported Annex I–ish vocabulary (hackathon)

Citizen-safe allowlist from architecture spike (protocol Annex I / TemporaryOahSystem-aligned). Exact code strings, value-set bindings, and component slice cardinalities: **[VERIFY]** against current `hl7-eu/oah` FSH before claiming profile conformance.

### In scope (protocol-lite)

| Area | Values / notes | FHIR mapping target (intended) |
|---|---|---|
| Macrophytes | A / P / E categories + non-native flags | `ObservationWithCompOah` macrophyte slices **[VERIFY]** |
| Riparian vegetation | Cover bins (protocol ordinals) + non-native | `#riparianVegetation` / components **[VERIFY]** |
| Hydromorphology | Present / Extensive / Absent **subset** | hydromorph / hydrology codes **[VERIFY]** |
| Sensory | Foam, colour, smell | `ObservationIndicatorsOah` / `#foam` etc. **[VERIFY]** |
| Site anchoring | One of five cities: Coimbra, Benevento, Ghent, Oslo, Toulouse | `LocationOah` **[VERIFY]** identifier system |
| Evidence | Photo(s) as evidence, not ecological truth | Media in domain; not lab Specimen |

**Optional later / external (not required for MVP core):** birds via Merlin (do not rebuild); invasive plant presence with expert/legal-class caution **[INFERENCE]** from validation matrix.

### Explicitly excluded from citizen AI-draftable / ConfirmGate citizen form core

- Diatoms / teratology indices  
- Macroinvertebrate **BMWP** / lab family ID as product fields  
- Fish (electrofishing)  
- Amphibians (permits / disease assays) — excluded from citizen AI draft; presence without permits is out of scope **[FACT]** validation matrix  
- Microbial diversity, fecal coliforms, pathogens, ARG/AMR  
- Diptera trap counts / overnight CO₂ protocols  
- Pharmaceuticals concentrations  
- HealthMeasure **disease prevalence** / clinical well-being as stream-selfie fields  

Physico-chem probe numerics: possible for trained CS with kits later; **not** inventable from photo. Out of initial hackathon Annex I categorical core unless explicitly added later with range rules.

---

## 8. Human authority model

| Layer | Authoritative for ecology / FHIR? | Role |
|---|---|---|
| **AI suggestion** | **Never** | Bounded enums / photo protocol QA / glossary only; labeled DRAFT |
| **System validation / flags** | Gate only | Can block confirm/finalize; cannot invent ecological truth |
| **Human-confirmed fields** | **Yes** (self-report / reviewer-adjudicated snapshot) | Confirm or reviewer accept freezes authority snapshot |
| **FHIR export** | Derived from confirmed snapshot only | Mapper + StructuralGuard; never from suggestions alone |

**HITL exact meaning:** No authoritative ecological value and no OAH-profiled FHIR Observation exists until a human performs `confirm` (or reviewer `accept`) on the packet’s field snapshot. Accept ≠ finalize; FHIR only after `FINALIZED`. See `docs/HITL-POLICY.md`.

Rubber-stamp failure mode (forbidden): one-click Confirm with AI values pre-filled as truth and no visible diff/flags.

---

## 9. AI product requirements

| Requirement | Detail |
|---|---|
| **NullAiAssist required** | Core demo and tests must pass with no API keys. **[IMPLEMENTED Phase 1]** `AiAssistPort` + `NullAiAssist`. |
| **Optional providers** | **[IMPLEMENTED Phase 8]** `FakeAiAssist` (offline) + `OptionalProviderAiAssist` (HTTP when configured). See `docs/AI-POLICY.md`. |
| **Allowed** | Bounded categorical suggestions (A/P/E, cover bins); optional flag-message explain; curated glossary stubs |
| **Prohibited** | BMWP / ecological quality class from photo; pathogen/AMR/pharma; disease/outbreak claims; composite eco or trust scores; auto-finalize FHIR; multi-agent “assessment crew” |

AI failure must not block submit → flag → confirm → finalize with rules-only path.

---

## 10. Impact / One Health

**Impact thesis (honest):** Usable CS inputs → hub tools and One Health intelligence are less starved by noise. **[INFERENCE]** from Track 3 + DSS needing structured inputs.

**Allowed language:** Citation-bound association language from OAH Policy Brief / factsheets (e.g. degraded urban streams *associated with* health/vector/pharma themes at study level). Template fills slots from **confirmed** fields only.

**Forbidden language:** Local causal claims (“this photo proves outbreak / mortality / infection risk”); diagnosis; inventing lab indicators to sound more One Health.

**Hackathon surface:** One templated sentence on the FHIR/finalize view — not a separate officer EvidenceBrief product in MVP.

---

## 11. Measurable success criteria

No trust-score metric. Prefer binary / countable demo and test outcomes:

| Criterion | Measure |
|---|---|
| Core path without AI | Submit → flags → confirm → finalize works with `NullAiAssist` |
| Bad evidence blocked | Demo/fixture: unsuitable photo or invalid vocab → hard/soft gate prevents confirm or finalize as designed |
| Human ≠ AI visible | Audit shows suggestion vs confirmed field when AI used |
| FHIR gate | Exporter refuses non-`FINALIZED`; exported Observations have `status=final` only; StructuralGuard + TemporaryOahSystem registry (`docs/FHIR-SPEC.md`) |
| Vocabulary honesty | Exported codes from TemporaryOahSystem / approved VS only — or honest refusal **[VERIFY]** |
| Provenance completeness | Append-only log can answer HITL audit questions (see REQUIREMENTS) |
| Five cities only | Seed/demo cities ∈ {Coimbra, Benevento, Ghent, Oslo, Toulouse} |
| Kill criteria absent | No photo→BMWP/pathogen, no composite trust score, no preliminary OAH Observations, AI not required |
| Deployed demo | Public web app URL + 3–5 min video for judging window |

Judging weights (context): Impact 30% / Innovation 20% / Technical 20% / UX 15% / Feasibility 15%. **[FACT]** Devpost Rules.

---

## 12. Explicit non-goals

- Composite **0–100 trust score** (or equivalent scalar “trust ML”)  
- **Photo scoring** of stream health / biotic indices / pathogen risk  
- **Disease diagnosis**, outbreak prediction, or HealthMeasure epi authoring from CS visits  
- **Blockchain** / Web3 provenance theater  
- **Multi-agent** swarms / LangChain agent crews as architecture  
- **Microservices** mesh for a solo hackathon week  
- Full **FHIR server** + SMART multi-tenant SaaS  
- Rebuild of **DSS / DipteraCAST / Resilience Map / GEOSSIP / CS app**  
- Full **IG validator green** claim on day one (StructuralGuard + fixtures first; validator port later)  
- Kitchen-sink: TrustGate + Review + EvidenceBrief + DSS + DipteraCAST as four polished UIs  

---

## Open Questions

1. Exact Annex I enum literals and which hydromorph subset is mandatory for MVP completeness rules — **[VERIFY]** protocols PDF + TemporaryOahSystem.  
2. Whether finalize is automatic after confirm or always an explicit export action — **Phase 2 default: explicit finalize** (see `docs/DOMAIN-MODEL.md`). UX may still present one button later without changing domain states.  
3. Reviewer auth model for hackathon (`/review` token vs open demo) — **[UNKNOWN]** ops preference.  
4. Official vs synthetic `Location` identifier system for five cities — **[VERIFY]** / label synthetic clearly if not official.  
5. Exact CS-app QC process today (to avoid duplicate UX claims) — **[UNKNOWN]**.  
6. Whether birds (Merlin) and IAP legal-class fields enter hackathon scope or stay post-MVP — spike lists as optional.  

---

*End of PRD v0.1 — DRAFT. Phase 2 domain model landed; see `docs/DOMAIN-MODEL.md`.*
