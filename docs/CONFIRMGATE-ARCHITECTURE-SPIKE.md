# ConfirmGate — Architecture Spike + BUILD-or-KILL Decision

**Date:** 21 Sep 2026  
**Role:** Hostile senior product architect + FHIR/domain validator  
**Scope:** Architecture decision only. **NO implementation.**  
**Workspace:** this repository  
**Priors challenged:** `docs/PRODUCT-VALIDATION.md`, `docs/RESEARCH-HACKATHON-OPPORTUNITY.md`, `AGENTS.md`, `docs/WIN-PLAN.md`  
**Legend:** **[FACT]** primary-cited · **[INFERENCE]** reasoned · **[UNKNOWN]** needs organizer/domain confirmation  

---

## Sources used (primary where possible)

| Source | URL / path | Use |
|---|---|---|
| Devpost + Rules (judging weights) | https://oneaquahealth-ieee-hackathon.devpost.com/ · `/rules` | Impact 30% / Innovation 20% / Technical 20% / UX 15% / Feasibility 15% **[FACT]** |
| Official hackathon page | https://www.oneaquahealth.eu/oneaquahealth-ieee-global-hackathon/ | Tracks, ecosystem constraints |
| Factsheets PDF | https://www.oneaquahealth.eu/app/uploads/2026/09/FactSheets_Combined_zenodo_f_citation_F_16092026.pdf · Zenodo doi [10.5281/zenodo.20345207](https://doi.org/10.5281/zenodo.20345207) | Lab/expert indicator methods |
| Field protocols PDF | https://www.oneaquahealth.eu/app/uploads/2026/09/Field-Sampling-protocols-OAH_citation_Final_16092026.pdf · doi [10.5281/zenodo.20344421](https://doi.org/10.5281/zenodo.20344421) | Annex I citizen/protocol-lite fields |
| OAH FHIR IG (FSH) | https://github.com/hl7-eu/oah | Profile constraints |
| CI build | https://build.fhir.org/ig/hl7-eu/oah | Published StructureDefinitions |
| Policy brief | https://www.oneaquahealth.eu/app/uploads/2026/05/OneAquaHealth-Policy-Brief.pdf | One Health claim language |
| Local validation | `docs/PRODUCT-VALIDATION.md` | Challenged prior (not authority) |
| Local opportunity research | `docs/RESEARCH-HACKATHON-OPPORTUNITY.md` | Challenged prior |
| Existing scaffold | `app/main.py` | Evidence of anti-patterns to kill |

### Material contradictions (do not paper over)

| Claim | Challenge | Verdict |
|---|---|---|
| `WIN-PLAN` / `AGENTS.md`: citizen checklist = habitat + macros + Diptera + WQ + well-being as factsheet-native | Factsheets I–XI are overwhelmingly lab/expert; habitat/hydromorph/macrophytes/riparian/foam live in **protocols Annex I** / FHIR TemporaryOahSystem; well-being is HealthMeasure epi, not a stream selfie field **[FACT]** validation matrix + FSH | **Prior is partially false** — must re-scope |
| Vision/LLM drafts meaningful OAH indicator values from photos | Indefensible for diatoms, BMWP, ARG, pathogens, electrofishing, CO₂ Diptera traps **[FACT]** factsheet methods | **Kill photo→score** |
| Scaffold emits `Observation.status = preliminary` when unconfirmed (`app/main.py`) | OAH `ObservationIndicatorsOah` **requires** `status = #final` **[FACT]** FSH + CI build | **Scaffold FHIR path is non-conformant** if claimed as OAH profile |
| Zenodo factsheets `20345206` vs `20345207` | PDF cites **20345207** **[FACT]** | Prefer 20345207 |
| Bundle TrustGate + Review + FHIR + EvidenceBrief + DSS + DipteraCAST as one hero product | Kitchen sink; four polished UIs fail Feasibility 15% for solo week **[INFERENCE]** | Ship **one primary + one secondary** |
| Composite 0–100 trust score | No published OAH method; CrowdWater uses multi-rater agreement, not a black-box scalar **[FACT]** PLOS One 2019 precedent cited in validation | **Ban composite score** |

---

# PART 1 — Attack ConfirmGate

Hostile questions answered without charity.

### Is it just a form?
**Risk: yes, if** the demo is “fill Annex I fields → download JSON.”  
**Survives if** the product’s non-obvious work is: (a) protocol-vocabulary constraint, (b) modular flag engine with coded reasons, (c) app-state ≠ FHIR-status lifecycle, (d) exporter that only emits IG-shaped `LocationOah` + `ObservationIndicatorsOah`/`ObservationWithCompOah` + `Provenance` after human authority, (e) explicit non-claim gates (no pathogen/diagnosis from photo).  
**[INFERENCE]** Domain judges (Feio, Datta) punish pretty forms that invent ecology; they reward honest QC + FHIR.

### Is it just a validation engine?
Validation is the **core**, not a decoration. Track 3 problem text is literally inconsistent/error-prone citizen observations **[FACT]** Devpost Track 3. A validation engine that ends in usable FHIR is the product; a dashboard that skips validation is the clone.

### Is FHIR decoration?
**Kill condition:** pretty-print generic Observation with free-text components (current scaffold pattern).  
**Survive condition:** map only to TemporaryOahSystem / OAH value sets; require `performer`, `effective`, `subject`→Location; never emit profiled Observation before confirm; include Provenance of confirmation.  
**[FACT]** Profile pins `status = #final`, `performer 1..`, `subject`→`LocationOah`, preferred `OahIndicatorsNoHealthOahVs` — https://github.com/hl7-eu/oah/blob/master/input/fsh/profiles/observation-indicators-oah.fsh · CI: https://build.fhir.org/ig/hl7-eu/oah/StructureDefinition-observation-indicators-oah.html

### Is AI decoration?
**If AI is required for the thesis, ConfirmGate fails scientific scrutiny.**  
Correct posture: rules/flags first; AI optional behind an interface for photo QA / enum suggestions / glossary. Demo must work with AI provider = null. Track 3 still allows validation + HITL without vision ecology **[INFERENCE]** from Track 3 wording + validation §F.

### Is HITL meaningful or rubber-stamp?
Meaningful only if: human can change every suggested enum; confirm is blocked when hard flags fire; audit shows AI suggestion ≠ confirmed value; overrides require reason codes. Rubber-stamp if “Confirm” is one click with no diff and AI values pre-filled as truth.

### Is the pain real?
**Yes for officers/curators; partial for citizens.** Pain: CS noise → decision tools ignore CS → One Health intelligence starves **[INFERENCE]** from Track 3 + DSS needing structured inputs. Exact CS-app QC process today: **[UNKNOWN]** (login wall). CrowdWater shows QA games improve accuracy **[FACT]** — precedent that quality products are real.

### Does it extend OAH or rebuild?
Extends: feeds cleaner inputs toward CS/Resilience/DSS/DipteraCAST without replacing them. Rebuild risk if branded as replacement CS mobile app or “our mosquito AI” (ENORA/Koutalieris conflict) **[FACT]** judges list + DipteraCAST existence.

### Judge usefulness (by weight)

| Criterion | Weight | ConfirmGate fit if scoped correctly |
|---|---|---|
| Impact & One Health | 30% | Medium–high **if** non-claim gates + one cited One Health sentence on finalize; weak if only “data quality middleware” with no health language |
| Innovation | 20% | Moderate — workflow/architecture novelty, not model novelty; beats LLM-wrapper clones |
| Technical | 20% | High — domain≠FHIR, flags, provenance, IG conformance |
| UX | 15% | Medium — must make flags/confirm/diff feel clear in 90s |
| Feasibility | 15% | High for solo modular monolith |

### Tech depth real or fake?
Real: protocol subset selection, flag engine, state machine, FHIR mapping, append-only audit. Fake: microservices, multi-agent swarm, blockchain, Isolation Forest on synthetic sensors, composite trust ML.

### 30-second clarity?
**Yes:** “Citizen stream reports are too noisy for One Health decisions. ConfirmGate rejects bad evidence, requires human confirmation, and only then writes OAH FHIR.”  
**No** if narration centers “AI scores the stream.”

### One-day clone risk?
High if vision-scoring StreamWitness. Lower if shallow cloners skip: Annex I enums, TemporaryOahSystem codes, status=final-only export, Provenance, flag reason vocabulary. **[INFERENCE]**

**Part 1 verdict:** ConfirmGate is **conditionally viable**. It dies as “form + GPT.” It lives as **observation integrity lifecycle ending in IG-conformant FHIR**.

---

# PART 2 — Product thesis

**ONE sentence:** ConfirmGate makes protocol-lite citizen stream observations usable for OneAquaHealth by applying explainable quality flags, requiring human confirmation, and emitting IG-conformant FHIR `Location`/`Observation` only after authority—never by AI auto-scoring.

---

# PART 3 — Real core (NOT everything)

| Keep | Drop for hackathon |
|---|---|
| **A.** Protocol-lite ingest (Annex I categorical/sensory + photo evidence) | Lab factsheet indicators (I–X except birds/IAP with training) as AI-draftable fields |
| **B.** Deterministic (+optional AI) quality flag engine | Composite 0–100 trust score |
| **C.** Human confirm/edit as authority gate | Auto-finalize FHIR |
| **D.** Domain `ConfirmedObservationPacket` store + audit | Multi-tenant SaaS / auth SSO |
| **E.** FHIR Bundle exporter (`LocationOah` + Observations + Provenance) | Full FHIR server + SMART auth |
| **F.** One One Health sentence template (cited, non-diagnostic) | Free-form LLM epidemiology |
| **G.** Secondary view: **reviewer queue OR officer brief** (pick one) | Both + DSS + DipteraCAST + maps + four personas |

**Recommended secondary:** Reviewer override for flagged packets (Track 3 HITL story). Officer brief = post-hackathon or thin templated panel on `/fhir` page, not a second product.

---

# PART 4 — Domain model (minimum entities)

Do **not** rubber-stamp names from research. Entities below are the smallest correct set.

### 4.1 `SiteRef` (seed, not user-created sprawl)

| Aspect | Definition |
|---|---|
| Purpose | Anchor observations to one of five OAH cities / demo reaches |
| Ownership | System seed data |
| Lifecycle | Immutable for hackathon (CRUD later) |
| Fields | `site_id`, `city` ∈ {Coimbra, Benevento, Ghent, Oslo, Toulouse}, `display_name`, optional `lat`/`lon`, `fhir_location_identifier` |
| Relationships | 1..* packets reference one SiteRef |
| Invariants | City must be one of five official; no invented sixth “official” city **[FACT]** |
| Mutators | Seed loader only |
| Audit | Seed version in Provenance entity |

### 4.2 `MediaAsset`

| Aspect | Definition |
|---|---|
| Purpose | Evidence photo(s), not ecological truth |
| Ownership | Submitting citizen (logical); system storage |
| Lifecycle | `uploaded` → `scrubbed` (EXIF policy applied) → `attached` → optional `rejected_as_evidence` |
| Fields | `media_id`, `content_type`, `storage_uri`, `sha256`, `width`/`height`, `exif_stripped` bool, optional `claimed_gps`, `captured_at` |
| Relationships | 0..* per packet |
| Invariants | Must not be required to invent indicator values; hard-flag if missing when rule requires bank/reach photo |
| Mutators | upload, scrub, attach, detach |
| Audit | upload + scrub events |

### 4.3 `ObservationPacket` (natural aggregate; rename of research’s ConfirmedObservationPacket — confirmation is a **state**, not a type)

| Aspect | Definition |
|---|---|
| Purpose | Single visit’s protocol-lite fields + media + flags + workflow state |
| Ownership | Citizen author until confirmed; curator/reviewer for overrides |
| Lifecycle | See Part 5 |
| Fields | `packet_id`, `site_ref_id`, `effective_at`, `submitter_display` (no unnecessary PII), `fields` (typed Annex I map), `suggestions` (optional AI, never authoritative), `flags[]`, `workflow_state`, `one_health_sentence` (template-filled after confirm), `fhir_bundle_id` nullable |
| Relationships | SiteRef, MediaAsset*, QualityFlag*, ProvenanceEvent*, optional FhirExport |
| Invariants | `suggestions` never copied to FHIR without human-confirmed `fields`; cannot enter `finalized` with unresolved hard flags; cannot claim lab codes |
| Mutators | create_draft, apply_flags, apply_suggestions, edit_fields, confirm, override_flag, reject, finalize_fhir, withdraw |
| Audit | Every mutator appends ProvenanceEvent |

**Why not `ObservationDraft` as root?** Draft is a state of the packet. Splitting Draft vs Confirmed as separate aggregates duplicates identity and invites dual-writes. **[INFERENCE]**

### 4.4 `FieldValue` (value object inside packet)

| Aspect | Definition |
|---|---|
| Purpose | One Annex I / TemporaryOahSystem-aligned datum |
| Fields | `code` (e.g. `#foam`, `#riparianVegetation`, hydromorph categories), `value` (enum/ordinal/quantity), `unit` optional, `source` ∈ {human, ai_suggestion_accepted, import}, `confidence` optional only on suggestions |
| Invariants | `code` ∈ allowlist for citizen-safe subset; value ∈ value set for that code |
| Mutators | set by edit_fields / accept_suggestion |

**Citizen-safe allowlist (hackathon):** macrophytes A/P/E + non-native flags; riparian cover bins; hydromorphology P/E/A subset; foam/colour/smell; optional birds species list via Merlin (external); optional invasive plant presence with expert-needed legal class flag.  
**Explicit exclude from citizen AI draft:** diatoms, macros BMWP, fish, amphibians (permits), microbes, coliforms, pathogens, ARGs, Diptera trap counts, pharmaceuticals, HealthMeasure disease prevalence. **[FACT]** validation matrix.

### 4.5 `QualityFlag`

| Aspect | Definition |
|---|---|
| Purpose | Structured fitness signal — **not** a score |
| Ownership | Flag engine (system); override owned by human roles |
| Lifecycle | `raised` → `acknowledged` → `resolved` \| `overridden` \| `stands` |
| Fields | `flag_id`, `rule_id`, `severity` ∈ {hard_reject, soft_block_finalize, warn}, `code` (machine), `message` (human), `evidence_refs` (field/media paths), `overridable` bool, `override_reason` optional |
| Relationships | Packet 1—*; rule definition in FlagEngine |
| Invariants | Hard flags block `confirm`/`finalize`; override requires reason + actor |
| Mutators | raise (engine), override, clear_on_revalidate |

### 4.6 `ProvenanceEvent` (append-only)

| Aspect | Definition |
|---|---|
| Purpose | Who did what, when, with which inputs/models |
| Ownership | System |
| Lifecycle | Append-only; never update/delete |
| Fields | `event_id`, `packet_id`, `at`, `actor_type` ∈ {citizen, reviewer, system, ai_provider}, `actor_id` opaque, `action`, `before`/`after` hashes or field diffs, `model_id`/`prompt_version` if AI, `rule_engine_version` |
| Relationships | Packet; later maps to FHIR Provenance on finalize |
| Invariants | Hash chain or monotonic sequence; no silent edits |

### 4.7 `FhirExport` (derived)

| Aspect | Definition |
|---|---|
| Purpose | Immutable snapshot of Bundle emitted at finalize |
| Ownership | System |
| Lifecycle | `generated` (terminal for that version); amendments create new export + amended Observations if ever needed (out of hackathon scope) |
| Fields | `export_id`, `packet_id`, `bundle_json`, `profile_set`, `validator_report` (hackathon: structural checks; full IG validator later), `generated_at` |
| Invariants | Only created from `finalized` packet; Observations always `status=final` |

### Rejected entities (for now)

| Rejected | Why |
|---|---|
| `TrustScore` | Fake scalar; use flags |
| `Agent` / multi-agent runtime | Theater |
| `QuestionnaireResponse` as required root | Valid FHIR pattern **[FACT]** but OAH IG has no Questionnaire profile; optional later, not required for ConfirmGate |
| Separate `EvidenceBrief` aggregate | Thin template field on packet / secondary view post-MVP |
| `DipteraPrediction` | Their product; feeder later |

---

# PART 5 — Smallest correct state machine

### Critical invariant

**App workflow state ≠ FHIR `Observation.status`.**  
OAH profiles constrain `status = #final` **[FACT]**. Therefore drafts live only in domain packets. FHIR resources are created at finalize, always final.

### States

```
RECEIVED → FLAGGED → AWAITING_CONFIRM → CONFIRMED → FINALIZED
                ↘ REJECTED
CONFIRMED → (optional) NEEDS_REVIEW → CONFIRMED | REJECTED
Any non-terminal → WITHDRAWN (citizen)
```

| State | Meaning | FHIR exists? |
|---|---|---|
| `RECEIVED` | Packet created; media attached; fields partial/complete | No |
| `FLAGGED` | Flag engine ran; hard/soft flags present | No |
| `AWAITING_CONFIRM` | Soft flags only or none; ready for human authority | No |
| `NEEDS_REVIEW` | Soft/hard-overridable flags require reviewer (secondary UX) | No |
| `CONFIRMED` | Human attested field values; ready to export | No (yet) |
| `FINALIZED` | Bundle written; terminal success | **Yes** |
| `REJECTED` | Hard reject or human reject; terminal failure | No |
| `WITHDRAWN` | Author withdrew; terminal | No |

### Transitions

| From → To | Actor | Preconditions | Validation | Side effects | Audit | Rollback |
|---|---|---|---|---|---|---|
| → RECEIVED | citizen/system | SiteRef valid; media policy OK | Schema of payload | Persist packet | `packet.created` | N/A |
| RECEIVED → FLAGGED | system | Always after ingest/edit | Run FlagEngine | Write flags[] | `flags.raised` | Re-run on edit |
| FLAGGED → REJECTED | system or reviewer | Any non-overridden `hard_reject` | — | Notify (optional) | `packet.rejected` | No (new packet) |
| FLAGGED → AWAITING_CONFIRM | system | No standing hard_reject | Completeness soft rules | Clear finalize lock | `flags.evaluated` | — |
| FLAGGED → NEEDS_REVIEW | system | Config: severity needs reviewer | — | Queue entry | `review.queued` | — |
| AWAITING_CONFIRM → CONFIRMED | citizen | Actor is author; fields valid enums; no hard flags | Confirm checklist UI completed | Freeze field snapshot hash | `human.confirmed` | Unconfirm only before FINALIZED → AWAITING_CONFIRM |
| NEEDS_REVIEW → CONFIRMED | reviewer | Reason codes; overrides recorded | Review form valid | Apply edits | `review.accepted` | — |
| NEEDS_REVIEW → REJECTED | reviewer | Reason code required | — | — | `review.rejected` | — |
| CONFIRMED → FINALIZED | system (on explicit export action or auto after confirm) | Confirmed hash unchanged; performer identity available; site identifier present | FHIR mapper structural validation | Write FhirExport; template One Health sentence | `fhir.exported` | No delete; amend path later |
| * → WITHDRAWN | citizen | Not FINALIZED | — | Soft-delete media optional | `packet.withdrawn` | No |

**Terminals:** `FINALIZED`, `REJECTED`, `WITHDRAWN`.

**Scaffold contradiction:** emitting FHIR with `preliminary` for unconfirmed sessions **violates** OAH profile pattern if labeled as `ObservationIndicatorsOah`. **Kill that pattern.**

---

# PART 6 — Flag engine

### Design

- **Modular rules:** each rule is a pure function `(packet) → list[QualityFlag]` with `rule_id`, version, severity.
- **Orchestrator:** runs rule set version `N`; concatenates flags; derives gate decision:
  - any standing `hard_reject` → cannot confirm
  - any `soft_block_finalize` without override → cannot finalize (may still edit)
  - `warn` only → allow confirm with display
- **NO 0–100 score.** Optional future: CrowdWater-style multi-rater agreement as a separate product.

### Rule modules (hackathon minimum)

| Module | Examples | Severity |
|---|---|---|
| `completeness` | Required Annex I subset missing | soft_block or hard depending on field |
| `vocabulary` | Value not in enum / TemporaryOahSystem allowlist | hard_reject |
| `nonclaim` | Attempt to set pathogen/ARG/BMWP/diagnosis fields | hard_reject |
| `geo` | City geofence mismatch; impossible travel vs prior visit | soft / hard configurable |
| `media` | Missing required photo; tiny image; wrong MIME | soft_block / hard |
| `media_heuristic` | Blur / non-outdoor heuristic (rules first) | warn / soft |
| `exif` | EXIF GPS vs claimed GPS mismatch | warn |
| `duplicate` | Same site + time window + similar fields | warn |
| `fhir_readiness` | Missing effective_at / performer / site identifier | soft_block_finalize |
| `ai_assist` (optional) | VLM suggests “not a stream” | warn / soft — never sole hard without human |

### Structured flag shape

```json
{
  "flag_id": "flg_…",
  "rule_id": "media.missing_bank_photo",
  "rule_version": "1.0.0",
  "severity": "soft_block_finalize",
  "code": "MEDIA_REQUIRED",
  "message": "Annex I requests bank/reach photo evidence for vegetation claims.",
  "evidence_refs": ["fields.riparianVegetation"],
  "overridable": true
}
```

---

# PART 7 — AI architecture

### Boundary

```
[Ingest UI] → [Packet] → [FlagEngine (deterministic)] → [Optional AiAssistPort] → [HITL Confirm] → [FhirExporter]
```

`AiAssistPort` methods (replaceable): `suggest_enums(packet, media) → Suggestions`, `assess_photo_protocol(media) → flags`, `glossary(term) → text`.  
Provider implementations: `NullAiAssist`, `HeuristicCvAssist`, `VlmAssist`.

### What survives scientific scrutiny

| Allowed | Why |
|---|---|
| Photo protocol QA flags | Does not invent ecology |
| Constrained enum suggestions (A/P/E, cover bins) with mandatory human confirm | Bounded output space |
| Glossary from curated factsheet/protocol text | Citation possible |
| External Merlin for birds | Already productized; don’t rebuild |

### REMOVE list (do not build)

- Photo → BMWP / ecological quality class  
- Photo → pathogen / AMR / pharmaceutical concentration  
- Photo → Diptera community / West Nile outbreak claim  
- Composite trust score ML  
- Multi-agent “assessment crew”  
- Free-form EvidenceBrief LLM without citation templates  
- Competing DipteraCAST prediction UI  

**AI is optional.** Acceptance tests must pass with `NullAiAssist`.

---

# PART 8 — HITL exact meaning + audit answers

### Exact meaning

Human-in-the-loop means: **no authoritative ecological value and no OAH-profiled FHIR Observation exists until a human actor performs `confirm` (or reviewer `accept`) on the packet’s field snapshot.** AI outputs are suggestions. Flags are advisory/blocking infrastructure, not authority.

### Audit answers (must be answerable from ProvenanceEvent log)

1. What did the citizen submit initially?  
2. What did AI suggest (model id, prompt/version, timestamp)?  
3. Which fields did the human change vs accept?  
4. Which flags were raised, overridden, and why?  
5. Who confirmed, when?  
6. Exactly which Bundle bytes were exported (hash)?  
7. Which rule-engine and mapper versions produced the export?

If any of these cannot be answered, HITL is theater.

---

# PART 9 — FHIR design

### Profiles used (real OAH only)

| Resource | Profile | When |
|---|---|---|
| Location | `LocationOah` | Always on finalize — identifier 1.., name 1.., mode=instance; position optional but lat/long required if present **[FACT]** location-oah.fsh |
| Observation (simple indicators) | `ObservationIndicatorsOah` | Foam/colour/smell, hydrology slices as separate Observations or components per mapper design; status=final; subject→Location; effective 1..; performer 1.. **[FACT]** |
| Observation (macrophytes/riparian) | `ObservationWithCompOah` | Component slices for macrophytes / nonNative / riparianVegetation **[FACT]** observation-with-component.fsh |
| Provenance | Base R4 Provenance | Confirmation + export activity; agents = citizen/reviewer; entity = packet hash / model if used |
| Specimen / Group / HealthMeasure | — | **Out of hackathon scope** (lab/epi) |

Codes from `TemporaryOahSystem` (`^experimental = true`) **[FACT]** oah-codeSystem.fsh — e.g. `#macrophytes`, `#riparianVegetation`, `#hydrology`, `#foam`.

### Domain → Bundle mapping

1. SiteRef → `LocationOah` (stable identifier under documented system, e.g. demo `https://streamwitness.local/location-id` clearly labeled synthetic if not official).  
2. Each confirmed FieldValue → Observation or component per profile rules (prefer few Observations matching IG examples style).  
3. Performer: PractitionerRole-lite or Organization display for hackathon — must populate `performer 1..`.  
4. Provenance.target → Observation(s) + Location; activity = “confirm and export”.  
5. Bundle type `collection` (or `document` only if Composition added — **don’t** invent Composition profile).

### Honesty constraint

Do **not** claim full IG validator green on day one. Claim: “Mapped to OAH profiles; structural required fields enforced; full validator in roadmap.” Architecture must allow plugging HAPI/validator later (Part 10).

---

# PART 10 — FHIR validation pipeline

```
Packet(CONFIRMED)
  → Mapper (pure)
  → StructuralGuard (required elements, code allowlist, status==final, cardinality)
  → (optional) IgValidatorPort.validate(bundle)  // Null / CLI / HAPI later
  → Persist FhirExport + surface report in UI
```

Hackathon: implement `StructuralGuard` thoroughly + golden JSON fixtures compared to IG examples shape.  
Post-hackathon: `IgValidatorPort` calling FHIR validator against published package `hl7.eu.fhir.oah`.

---

# PART 11 — Append-only provenance

- Store: append-only log table/file (`provenance_events.jsonl` acceptable for MVP).  
- Each event: monotonic `seq`, `packet_id`, `at`, `actor`, `action`, `payload_hash`, optional `diff`.  
- Packet row may hold `current_state` + `fields` for UX, but authoritative history is the log.  
- On finalize: emit FHIR Provenance summarizing confirm + export; keep app log as super-set (flags, AI versions).  
- No UPDATE/DELETE on events. Corrections = new events.

---

# PART 12 — Security / privacy

| Topic | Policy |
|---|---|
| Photos | May contain faces, license plates, home locations — treat as personal data |
| EXIF | Strip GPS/device identifiers by default before persistence; if retaining for science, require explicit opt-in + flag |
| Claimed GPS | Store separately from EXIF; never publish precise citizen home coords in public demo |
| Access | Hackathon: no public listing of others’ packets; unguessable packet ids; optional simple curator token for `/review` |
| Retention | Document wipe of uploads after judging; no secrets in git |
| AI providers | If cloud VLM used: don’t send exact home GPS; disclose in README AI disclosure |
| Non-claim | UI copy forbids medical diagnosis |

**[UNKNOWN]** GDPR role of OAH cities for production — out of hackathon legal scope but demo must not leak PII.

---

# PART 13 — UX structure

### Primary: Citizen ConfirmGate (`/upload` → confirm surface)

1. Pick city/site (5 cities).  
2. Attach photo(s) + fill Annex I categorical/sensory fields (not lab checklist).  
3. See flag panel (pass / warn / block) with plain reasons.  
4. See optional AI suggestions clearly labeled DRAFT; edit enums.  
5. Confirm → receipt.  
6. View/download FHIR Bundle on `/fhir` only after confirm.

### ONE secondary: Reviewer desk (`/review`)

Queue of `NEEDS_REVIEW` / overridden-hard candidates; accept/edit/reject with reason codes; audit visible.

**Not both** officer brief and reviewer as polished UIs. Officer gets a single templated One Health sentence on the FHIR page (Impact 30% without second app).

---

# PART 14 — 90s honest demo

1. **0–15s:** “Track 3: citizen stream reports are inconsistent, so One Health tools can’t trust them.”  
2. **15–35s:** Submit blurry sidewalk photo → hard/soft media flags → blocked.  
3. **35–70s:** Submit Coimbra reach photo + Annex I vegetation/foam fields → optional AI suggests A/P/E → human changes one field → Confirm.  
4. **70–90s:** Show audit diff (AI ≠ human) + FHIR Bundle with `status: final`, TemporaryOahSystem codes, One Health sentence that **cites** policy-brief association language (no local death claim). Say: “Human remains the authority. We do not score BMWP from photos.”

---

# PART 15 — Winning differentiator

Emerges from the problem, not branding:

**The missing OAH wedge is a scientifically humble observation lifecycle that refuses to launder photo-AI into lab indicators, proves human authority with audit, and operationalizes the draft FHIR IG’s `status=final` constraint.**

Competitors will ship dashboards and GPT stream scores. ConfirmGate ships **usable, protocol-aligned, IG-shaped observations**.

---

# PART 16 — Modular monolith vs SOA vs microservices

**Recommend: modular monolith.**

| Option | Verdict |
|---|---|
| Microservices | Fake complexity; solo week death; Feasibility 15% tank |
| SOA / separate deployables | Unnecessary until embed beside CS app |
| Modular monolith | One FastAPI process; packages/modules with typed ports; extract library later |

Modules: `ingest`, `flags`, `ai_port`, `workflow`, `fhir_export`, `provenance`, `web`.

---

# PART 17 — Tech stack (justified)

| Dependency | Why |
|---|---|
| **Python 3.11+** | Solo speed; FHIR JSON; existing scaffold |
| **FastAPI** | Simple HTML + JSON; deployable; no SPA complexity required |
| **Jinja2 server-rendered HTML** | UX 15% without React build; hackathon reliability |
| **Pydantic v2** | Domain invariants + request validation |
| **JSON/file or SQLite** | Persist packets + append-only log without ops tax; Postgres post-hackathon |
| **Local object dir / optional S3** | Media storage; strip EXIF with Pillow |
| **Pillow** | Image heuristics + EXIF scrub |
| **pytest** | Flag engine + mapper tests before UI polish |
| **Optional OpenAI/Anthropic SDK behind AiAssistPort** | Only after Null path works |
| **No** Streamlit, LangChain agents swarm, Kubernetes, blockchain, Isolation Forest |

Keep close to existing scaffold stack (`requirements.txt`) but **replace** indicator model and FHIR preliminary anti-pattern.

---

# PART 18 — Test strategy before implementation

Write/plan tests **before** features:

1. **Flag unit tests:** each rule — missing field, bad enum, nonclaim pathogen attempt, EXIF mismatch fixture.  
2. **State machine tests:** illegal transitions raise; hard flag blocks confirm; confirm then mutate fields blocked without re-open.  
3. **Mapper tests:** confirmed packet → Bundle with status=final, performer present, codes from allowlist; unconfirmed → exporter refuses.  
4. **Provenance tests:** edit produces append; no update in place.  
5. **AI port tests:** Null provider; fake provider suggestions never appear in Bundle without accept+confirm.  
6. **Golden fixtures:** 2–3 packets (reject, warn+confirm, review path) checked into `tests/fixtures/`.  
7. **Manual script:** 90s demo checklist as `docs/DEMO-SCRIPT.md` (post-approval).

---

# PART 19 — Repo / docs structure (only valuable docs)

```
app/
  domain/          # packet, flags, state machine
  flags/           # rules
  fhir/            # mapper + structural guard
  ai/              # AiAssistPort + null
  provenance/
  web/             # routes + templates
docs/
  CONFIRMGATE-ARCHITECTURE-SPIKE.md  # this decision
  PRODUCT-VALIDATION.md              # keep
  RESEARCH-HACKATHON-OPPORTUNITY.md  # keep
  WIN-PLAN.md                        # update after approval (correct indicators)
  SUBMISSION.md                      # Devpost draft notes
  DEMO-SCRIPT.md                     # after build starts
  HITL-POLICY.md                     # short, submission-facing
tests/
README.md                            # Track, live URL, HITL, FHIR, AI disclosure
```

**Do not** create architecture.md, agents.md sprawl, ADR spam, or microservices diagrams.

---

# PART 20 — Hackathon release vs post-hackathon

> The 29 Sep date reflects the original schedule. Current Devpost deadline: **4 Oct 2026, 9:00 PM PDT (5 Oct 2026, 09:30 IST)**.

| Hackathon (submit 29 Sep 2026) | Post-hackathon |
|---|---|
| Annex I subset only | Expand with kit-assisted WQ numerics |
| Structural FHIR guard | Full IG validator + FHIR server |
| Null/optional AI | Calibrated photo QA |
| Reviewer secondary UX | CS-app embed / API |
| SQLite/JSON | Postgres + object storage |
| Synthetic site ids labeled | Official location-id alignment |
| One Health sentence template | EvidenceBrief module |
| No DSS/DipteraCAST | Descriptor feeder adapters if I/O known |

---

# FINAL DECISION OUTPUT

## 1. ConfirmGate viability verdict

**CONDITIONALLY VIABLE → recommend BUILD** under the constraints in this spike.  
**Not viable** as vision stream-scorer, composite trust product, or kitchen-sink TrustGate+Brief+DSS+DipteraCAST.

Sunk research cost is **not** the reason. The reason: Track 3’s actual problem (inconsistent CS) + OAH’s actual gap (no HITL finalize path into IG-shaped FHIR) + scientific honesty about photo limits align with a shippable solo product in one week.

## 2. Product thesis

ConfirmGate makes protocol-lite citizen stream observations usable for OneAquaHealth by applying explainable quality flags, requiring human confirmation, and emitting IG-conformant FHIR `Location`/`Observation` only after authority—never by AI auto-scoring.

## 3. Core workflow

Ingest (city + Annex I fields + photo) → FlagEngine → (optional AI suggestions) → Human confirm/edit → optional Reviewer if flagged → Finalize Bundle (`LocationOah` + Observations `status=final` + Provenance) + templated One Health sentence → download/view.

## 4. Core domain model

`SiteRef`, `MediaAsset`, `ObservationPacket` (with `FieldValue`s), `QualityFlag`, `ProvenanceEvent`, `FhirExport`. No `TrustScore`. Confirmation is a state, not a separate aggregate type.

## 5. State machine

`RECEIVED → FLAGGED → AWAITING_CONFIRM → CONFIRMED → FINALIZED` with `NEEDS_REVIEW`, `REJECTED`, `WITHDRAWN` terminals/branches. App state ≠ FHIR status; FHIR exists only at `FINALIZED` and only as `final`.

## 6. Flag engine design

Modular pure rules → structured flags with severity; gate decisions from flags; no composite score; versions on rule sets.

## 7. AI boundary

Optional `AiAssistPort`; Null provider required; suggestions never authoritative; REMOVE photo→index/pathogen/trust-score/agents.

## 8. FHIR architecture

Domain packet → mapper → StructuralGuard → Bundle of `LocationOah` + `ObservationIndicatorsOah` / `ObservationWithCompOah` + base `Provenance`; TemporaryOahSystem codes; never preliminary OAH-profile Observations.

## 9. Provenance architecture

Append-only event log for all mutators; FHIR Provenance on export summarizing confirmation; answer the seven HITL audit questions.

## 10. UX structure

Primary citizen ConfirmGate; secondary reviewer desk; One Health sentence on FHIR view (not a separate officer product in hackathon).

## 11. Architecture (repo/modules)

Modular monolith (FastAPI): `domain`, `flags`, `ai`, `fhir`, `provenance`, `web`.

## 12. Testing strategy

Flag/state/mapper/provenance/AI-port unit tests + golden fixtures **before** UI polish; exporter refuse-unconfirmed test mandatory.

## 13. Security/privacy

EXIF strip default; no public PII; opaque ids; disclose AI data flows; non-claim UI; retention wipe after judging.

## 14. 90-second demo

Bad photo blocked → good Annex I packet → human edits AI suggestion → audit diff → final FHIR Bundle + cited One Health sentence.

## 15. Hackathon scope

Five cities seed; Annex I citizen-safe fields only; flag engine; confirm; `/fhir` download; `/review` minimal; optional AI; deploy web app; video 3–5 min; public GitHub.  
**Out:** lab indicators AI, trust score, DSS/DipteraCAST, maps, blockchain, microservices, full IG validator (architecture ready).

## 16. Post-hackathon roadmap

IG validator; CS embed API; calibrated CV; EvidenceBrief module; descriptor feeders; Postgres; official Location identifiers; multilingual glossaries.

## 17. Kill criteria

Kill or refuse to submit if the prototype:

1. Auto-scores stream health / BMWP / pathogen risk from photos.  
2. Emits OAH-profiled FHIR without human confirm.  
3. Ships a composite 0–100 trust score as the product.  
4. Uses free-text fake codes instead of TemporaryOahSystem / OAH value sets.  
5. Emits `status=preliminary` while claiming `ObservationIndicatorsOah` conformance.  
6. Rebuilds CS app / Resilience Map / GEOSSIP / DSS / DipteraCAST as the hero.  
7. Markets “our mosquito prediction AI” against DipteraCAST.  
8. Requires AI provider to complete the core demo.

## 18. Final recommendation

# BUILD

**Why BUILD (not sunk-cost):**

- **Novelty:** Operationalizes the hard FHIR draft-vs-`final` tension + protocol-lite honesty that clones will skip.  
- **Technical depth:** Flag engine + state machine + IG-shaped export + provenance — demanded by the problem.  
- **OAH alignment:** Extends CS quality toward hub tools; uses their IG and Annex I vocabulary; Five cities; Track 3 literal.  
- **UX:** One clear authority moment (confirm) with visible flags/diff.  
- **Demo strength:** Reject → confirm → final JSON is crystal clear in 90s and honest under ecological scrutiny.

**If human rejects BUILD:** Prefer **EvidenceBrief-only** (Impact 30%, thinner Technical) or **stop** rather than build vision-scoring StreamWitness as currently written in `WIN-PLAN.md`.

---

# Implementation contract (future Cursor work — after human approval)

When implementation is approved, each change set follows this 13-step sequence:

1. **Understand** — restate the packet/flag/FHIR invariant touched by the task.  
2. **Inspect** — read current modules/tests/fixtures before editing.  
3. **Modules** — name which modular-monolith packages change (`domain`/`flags`/`fhir`/…).  
4. **Approach** — smallest design that preserves app-state ≠ FHIR-status.  
5. **Risks** — scientific overclaim, profile violation, PII/EXIF, AI leakage into authority.  
6. **Acceptance** — write concrete pass/fail checks (incl. Null AI path).  
7. **Smallest change** — implement only what the acceptance requires.  
8. **Tests** — add/adjust unit + fixture tests first or with the change.  
9. **Run** — execute targeted pytest + manual path for the demo beat.  
10. **Review** — hostile self-check against kill criteria §17.  
11. **Refactor** — only if required for clarity; no speculative architecture.  
12. **Docs** — update HITL/FHIR/AI disclosure and README live URL notes only when behavior changes.  
13. **Next** — propose the single next spike/task; do not expand scope silently.

---

**AWAITING HUMAN APPROVAL — DO NOT IMPLEMENT**
