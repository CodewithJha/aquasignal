# ConfirmGate — Engineering Requirements

Status: DRAFT  
Version: 0.1  
Date: 21 Sep 2026  
Owner: ConfirmGate  
Source of truth: CONFIRMGATE-ARCHITECTURE-SPIKE.md  

**Companion:** `docs/PRD.md` (what / for whom / why). This file is for implementation and testing only.  
**Phase rule:** Do **not** implement Phase 2+ from this document until human approval. Phase 1 scaffolding facts are marked **[IMPLEMENTED Phase 1]** where verified in the current repo.

**Legend:** **[VERIFY]** = confirm against OAH FHIR IG / protocols before claiming conformance. **[UNKNOWN]** / **[INFERENCE]** as needed.

---

## 0. Implemented Phase 1 baselines (do not regress)

| ID | Fact in repo | Status |
|---|---|---|
| AI-001 | `AiAssistPort` + `NullAiAssist` (no API keys) | **[IMPLEMENTED Phase 1]** |
| AI-002 | Suggestions not authoritative | **[IMPLEMENTED Phase 8]** |
| AI-003 | Cannot bypass HITL | **[IMPLEMENTED Phase 8]** |
| AI-004 | Model/version recorded | **[IMPLEMENTED Phase 8]** |
| AI-005 | AI failure does not block core | **[IMPLEMENTED Phase 8]** |
| AI-006 | No prohibited claims | **[IMPLEMENTED Phase 8]** |
| FHIR-003 | `export_bundle` raises `FhirExportRefused` unless `workflow_state == FINALIZED` | **[IMPLEMENTED Phase 1+5]** |
| FHIR-002 (partial) | Exporter never sets `Observation.status = preliminary`; Phase 1 stub emits no Observation | **[SUPERSEDED Phase 5]** — Observations exported with `status=final` only |
| — | Packages: `app/domain`, `app/flags`, `app/ai`, `app/fhir`, `app/provenance`, `app/web` | **[IMPLEMENTED Phase 1]** |
| FR-020–030 (core) | `ObservationPacket` mutators + illegal-transition enforcement; confirmation snapshot hash; AI cannot confirm/finalize | **[IMPLEMENTED Phase 2]** |
| FR-031 | Unconfirm `CONFIRMED → AWAITING_CONFIRM` | **Deferred** — not in Phase 2 exact transition matrix (`docs/DOMAIN-MODEL.md`) |
| FR-010–013 (core) | `DeterministicFlagEngine` + rule modules; versioned; re-eval after edit; no trust score | **[IMPLEMENTED Phase 3]** — see `docs/FLAG-ENGINE.md` |
| FR-012 media/exif/duplicate depth | Full image/EXIF/persistence-backed duplicate | **Bounded Phase 3** via null ports until Phase 4/9 |

---

## 1. Functional requirements — submission

### FR-001 — Site-bound submission
The system shall accept a new observation packet only when `site_ref` resolves to a seeded site whose `city` ∈ {Coimbra, Benevento, Ghent, Oslo, Toulouse}.

**Acceptance**  
- **Given** a submit payload with city/site outside the five OAH cities  
- **When** create/submit is invoked  
- **Then** the request is rejected and no packet enters `RECEIVED`

### FR-002 — Protocol-lite field payload
The system shall persist citizen fields only from the approved allowlist (macrophytes A/P/E + non-native; riparian cover bins; hydromorph P/E/A subset; foam/colour/smell). Exact code/value bindings **[VERIFY]**.

**Acceptance**  
- **Given** a payload containing an excluded indicator (e.g. BMWP, pathogen, disease prevalence)  
- **When** validation/flagging runs  
- **Then** a `nonclaim` (or equivalent) **hard** flag is raised and authoritative field storage for that code is refused

### FR-003 — Media as evidence
The system shall allow 0..* photo attachments as evidence assets (content type, hash, scrub metadata). Photos shall not be treated as automatic indicator values.

**Acceptance**  
- **Given** a packet with only a photo and no invented lab codes  
- **When** FlagEngine runs  
- **Then** no BMWP/pathogen/disease field is created from the photo alone

### FR-004 — Opaque packet identity
Each packet shall receive an unguessable opaque `packet_id` at creation.

**Acceptance**  
- **Given** two successive submissions  
- **When** packets are created  
- **Then** ids are unique and not sequential guessable integers (e.g. UUID/hex)

---

## 2. Functional requirements — validation / flags

### FR-010 — FlagEngine orchestration
After ingest or field/media edit, the system shall run a versioned FlagEngine that returns zero or more structured `QualityFlag` records (no composite 0–100 score).

**Acceptance**  
- **Given** a valid empty/minimal packet  
- **When** FlagEngine runs  
- **Then** output is a list of flags with `rule_id`, `severity`, `code`, `message` — and no trust-score field exists

### FR-011 — Flag severities
Each flag severity shall be one of: `hard_reject`, `soft_block_finalize`, `warn`.

**Acceptance**  
- **Given** flags of each severity class (fixtures)  
- **When** gate decision is computed  
- **Then** standing `hard_reject` blocks confirm; standing `soft_block_finalize` without override blocks finalize; `warn` alone does not block confirm

### FR-012 — Minimum rule modules
Hackathon minimum modules: `completeness`, `vocabulary`, `nonclaim`, `geo` (configurable), `media`, `media_heuristic`, `exif`, `duplicate`, `fhir_readiness`; optional `ai_assist` never sole hard without human path. **[INFERENCE]** module list from spike Part 6.

**Acceptance**  
- **Given** fixtures for missing required field, bad enum, nonclaim pathogen attempt, missing required photo  
- **When** FlagEngine runs  
- **Then** each fixture raises the expected `rule_id` family and severity class

### FR-013 — Revalidation on edit
Editing fields or media shall clear stale flags and re-run FlagEngine.

**Acceptance**  
- **Given** a packet in `FLAGGED` with a completeness flag  
- **When** the missing field is supplied  
- **Then** that flag is cleared or replaced by a fresh evaluation event (append-only)

---

## 3. Functional requirements — workflow states

States: `RECEIVED`, `FLAGGED`, `AWAITING_CONFIRM`, `NEEDS_REVIEW`, `CONFIRMED`, `FINALIZED`, `REJECTED`, `WITHDRAWN`.

**Invariant FR-020:** Domain `workflow_state` is never written into FHIR as a substitute for creating Observations early. FHIR resources exist only after successful finalize.

### FR-021 — Enter RECEIVED
**Acceptance**  
- **Given** valid SiteRef and media policy OK  
- **When** packet is created  
- **Then** state = `RECEIVED` and provenance `packet.created` is appended

### FR-022 — RECEIVED → FLAGGED
**Acceptance**  
- **Given** a packet in `RECEIVED`  
- **When** FlagEngine completes after ingest/edit  
- **Then** state = `FLAGGED` and `flags.raised` is audited

### FR-023 — FLAGGED → REJECTED (hard)
**Acceptance**  
- **Given** standing non-overridden `hard_reject`  
- **When** gate evaluation runs (system) or reviewer hard-rejects  
- **Then** state = `REJECTED` (terminal); FHIR export remains impossible

### FR-024 — FLAGGED → AWAITING_CONFIRM
**Acceptance**  
- **Given** no standing `hard_reject`  
- **When** flags are evaluated as soft/warn/none  
- **Then** state = `AWAITING_CONFIRM`

### FR-025 — FLAGGED → NEEDS_REVIEW
**Acceptance**  
- **Given** configuration that selected severities require reviewer  
- **When** evaluation selects escalation  
- **Then** state = `NEEDS_REVIEW` and a queue entry is recorded

### FR-026 — AWAITING_CONFIRM → CONFIRMED (citizen)
**Acceptance**  
- **Given** actor is packet author; fields valid against allowlist; no standing hard flags  
- **When** citizen confirms  
- **Then** state = `CONFIRMED`; field snapshot hash frozen; `human.confirmed` audited; still **no** FHIR Observation

### FR-027 — NEEDS_REVIEW → CONFIRMED | REJECTED (reviewer)
**Acceptance**  
- **Given** packet in `NEEDS_REVIEW`  
- **When** reviewer accepts (with reason codes / overrides recorded) or rejects (reason required)  
- **Then** state becomes `CONFIRMED` or `REJECTED` respectively; audit records actor and reasons

### FR-028 — CONFIRMED → FINALIZED
**Acceptance**  
- **Given** confirmed snapshot hash unchanged; performer identity available; site identifier present; no blocking soft flags without override  
- **When** finalize/export action succeeds StructuralGuard  
- **Then** state = `FINALIZED`; `FhirExport` persisted; One Health sentence template filled; `fhir.exported` audited

### FR-029 — Withdraw
**Acceptance**  
- **Given** packet not in `FINALIZED`  
- **When** author withdraws  
- **Then** state = `WITHDRAWN` (terminal); export remains refused

### FR-030 — Illegal transitions
The system shall reject transitions not listed in the architecture spike Part 5 table (e.g. `RECEIVED → FINALIZED`, `REJECTED → CONFIRMED`, mutate confirmed fields without re-open).

**Acceptance**  
- **Given** each illegal pair in a Phase 2 test matrix  
- **When** transition is attempted  
- **Then** operation fails; state unchanged; optional audit of denied attempt

### FR-031 — Unconfirm before finalize
**Acceptance**  
- **Given** `CONFIRMED` and not `FINALIZED`  
- **When** authorized unconfirm occurs  
- **Then** state returns to `AWAITING_CONFIRM` (or re-enters flag path on edit) and snapshot lock is released per design

---

## 4. HITL requirements

### HITL-001 — Confirm is authority
No authoritative ecological field set shall be marked confirmed without an explicit human confirm/accept action.

**Acceptance**  
- **Given** AI suggestions populated on a packet  
- **When** export is attempted without confirm/finalize  
- **Then** export is refused and suggestions are not present as Observation values

### HITL-002 — Human can change every suggested enum
**Acceptance**  
- **Given** AI suggested value V for field F  
- **When** human sets F to W ≠ V and confirms  
- **Then** confirmed snapshot contains W; provenance records accept/edit diff

### HITL-003 — Hard flags block confirm
**Acceptance**  
- **Given** standing `hard_reject`  
- **When** citizen attempts confirm  
- **Then** confirm is rejected

### HITL-004 — Overrides require reason
**Acceptance**  
- **Given** an overridable flag  
- **When** human overrides  
- **Then** `override_reason` and actor are required and audited; silent override is impossible

### HITL-005 — Reviewer escalation desk
Secondary UX shall list `NEEDS_REVIEW` (and configured override candidates) with accept/edit/reject + reason codes.

**Acceptance**  
- **Given** at least one `NEEDS_REVIEW` packet  
- **When** reviewer opens `/review` queue  
- **Then** packet appears; decision without reason code fails validation

---

## 5. FHIR requirements

### FHIR-001 — No OAH Observation before finalization
The system shall not create or return OAH-profiled `Observation` resources for packets that are not `FINALIZED`.

**Acceptance**  
- **Given** packet in any state except `FINALIZED`  
- **When** FHIR export/read for Observations is requested  
- **Then** operation refuses or returns no Observation resources (prefer refusal)

### FHIR-002 — status = final only
Every exported OAH-profiled Observation shall have `status` = `final`. The system shall never emit `preliminary` for app-generated OAH Observations.

**Acceptance**  
- **Given** a successful finalize with mapped Observations  
- **When** Bundle is inspected  
- **Then** every Observation.status == `final` and none == `preliminary`  
- Note: Phase 5 exports LocationOah + ObservationIndicatorsOah from the confirmation snapshot with `status=final` only. See `docs/FHIR-SPEC.md`.

### FHIR-003 — Refuse non-finalized export
`export_bundle(packet)` shall refuse unless `workflow_state == FINALIZED`.

**Acceptance** — **[IMPLEMENTED Phase 1]**  
- **Given** each non-finalized state  
- **When** `export_bundle` is called  
- **Then** `FhirExportRefused` (or equivalent) is raised

### FHIR-004 — LocationOah requirements
On finalize, Bundle shall include a Location conforming to `LocationOah` required elements: `identifier` 1.., `name` 1.., `mode` = instance; if `position` present, lat/long required. **[VERIFY]** FSH.

**Acceptance**  
- **Given** a finalized packet with SiteRef  
- **When** mapper + StructuralGuard run  
- **Then** Location satisfies required cardinalities or export fails closed

### FHIR-005 — Observation profile requirements
Mapped indicators shall target `ObservationIndicatorsOah` and/or `ObservationWithCompOah` as appropriate: `subject` → Location; `effective[x]` 1..; `performer` 1..; status final. **[VERIFY]**

**Acceptance**  
- **Given** confirmed foam/colour/smell and/or macrophyte-riparian fields  
- **When** export succeeds  
- **Then** StructuralGuard asserts performer, effective, subject reference, and profile-required shapes — or refuses

### FHIR-006 — Codes from approved OAH vocabulary
Observation codes/components shall use TemporaryOahSystem / approved OAH value sets only — no free-text invented codes as if they were IG codes. **[VERIFY]**

**Acceptance**  
- **Given** confirmed field with allowlisted code  
- **When** Bundle is produced  
- **Then** coding.system/code match allowlist fixtures; unknown codes fail StructuralGuard

### FHIR-007 — Provenance on confirm/export
Finalize shall record **internal** append-only audit events for confirm + export (`fhir.exported`, `fhir.export_digest` with `bundle_hash` + `mapper_version`).

**Phase 5 decision:** The OAH IG defines **no Provenance profile** and does not require a FHIR `Provenance` resource. ConfirmGate therefore does **not** emit FHIR Provenance in the Bundle (prefer refusal of fabricated IG artifacts). HITL Q6/Q7 are answered from internal provenance. Revisit if the IG later profiles Provenance or product policy explicitly requires base R4 Provenance.

**Acceptance**  
- **Given** successful finalize after human confirm + export  
- **When** audit is queried  
- **Then** `bundle_hash` and `mapper_version` are present on export provenance; Bundle contains Location + Observation(s) only (no invented Provenance resource)

### FHIR-008 — Honesty constraint
Do not claim full IG validator green until `IgValidatorPort` + real mapping exist. StructuralGuard + golden fixtures are the hackathon bar.

**Acceptance**  
- **Given** Phase FHIR export  
- **When** UI/docs describe conformance  
- **Then** copy states structural enforcement / mapped-to-profiles — not “validator green” — unless validator port is actually wired

### FHIR-009 — Bundle type
Prefer Bundle `type` = `collection`. Do not invent an OAH Composition profile. **[VERIFY]** if document Bundles become required later.

---

## 6. AI requirements

### AI-001 — NullAiAssist required
**[IMPLEMENTED Phase 1]** Default provider shall be `NullAiAssist`; core path works with zero API keys / network.

**Acceptance**  
- **Given** AI provider = Null  
- **When** suggest_enums / assess_photo_protocol / glossary are called  
- **Then** calls succeed without external I/O; demo path remains usable

### AI-002 — Suggestions not authoritative
**[IMPLEMENTED Phase 8]** AI outputs shall live in `suggestions` (or equivalent), never silently copied into confirmed `fields` or FHIR.

**Acceptance**  
- **Given** non-null provider returns enum suggestion  
- **When** human confirms without accepting  
- **Then** confirmed fields exclude suggestion unless explicitly accepted

### AI-003 — Cannot bypass HITL
**[IMPLEMENTED Phase 8]** No AI action may transition a packet to `CONFIRMED` or `FINALIZED`.

**Acceptance**  
- **Given** any AI port response  
- **When** only AI methods are invoked  
- **Then** workflow_state remains unchanged w.r.t. confirm/finalize

### AI-004 — Model/version recorded
**[IMPLEMENTED Phase 8]** When AI runs, provenance shall record `model_id` and prompt/provider version (or `null` for NullAiAssist).

**Acceptance**  
- **Given** an AI suggestion event  
- **When** provenance is queried  
- **Then** model_id/version fields are present

### AI-005 — AI failure does not block core
**[IMPLEMENTED Phase 8]**  
**Acceptance**  
- **Given** AI provider raises/unavailable  
- **When** citizen continues rules-only path  
- **Then** flag → confirm → finalize still completable

### AI-006 — No prohibited claims
**[IMPLEMENTED Phase 8]** AI shall not produce BMWP, pathogen/AMR/pharma concentrations, disease/outbreak, composite eco/trust scores, or auto-finalize instructions as product outputs.

**Acceptance**  
- **Given** provider implementation under test  
- **When** contract tests run  
- **Then** prohibited output channels are absent; nonclaim flags fire if user attempts excluded fields

See also `docs/AI-POLICY.md`.

---

## 7. Provenance requirements

### PROV-001 — Append-only
Provenance events shall be append-only (no UPDATE/DELETE). Corrections = new events.

**Acceptance**  
- **Given** an existing event  
- **When** correction is needed  
- **Then** a new event is appended; original bytes/record remain

### PROV-002 — Answer audit questions
From the append-only log alone, the system shall answer:

**Spike Part 8 (mandatory seven):**  
1. What did the citizen submit initially?  
2. What did AI suggest (model id, prompt/version, timestamp)?  
3. Which fields did the human change vs accept?  
4. Which flags were raised, overridden, and why?  
5. Who confirmed, when?  
6. Exactly which Bundle bytes were exported (hash)?  
7. Which rule-engine and mapper versions produced the export?

**Engineering extensions (ten total) — [INFERENCE] beyond spike’s seven:**  
8. Who rejected or withdrew, when, and with what reason (if any)?  
9. Which media assets were attached, and was EXIF scrub applied?  
10. Which reviewer (if any) accepted/edited/rejected, with reason codes?

**Acceptance**  
- **Given** a golden fixture journey (reject; warn+confirm+export; review path)  
- **When** audit API/query runs  
- **Then** answers 1–10 are populated or explicitly recorded as N/A (e.g. no AI → Q2 N/A)

---

## 8. Security & privacy requirements

### SEC-001 — EXIF policy
By default, strip GPS/device identifiers from persisted photos before durable storage. Retaining EXIF for science requires explicit opt-in + flag. **[INFERENCE]** from spike Part 12.

**Acceptance**  
- **Given** JPEG with GPS EXIF  
- **When** uploaded under default policy  
- **Then** stored asset has `exif_stripped=true` and GPS not present in stored file metadata

### SEC-002 — Claimed GPS vs EXIF
Claimed GPS shall be stored separately from EXIF; mismatches may raise `exif` flags.

**Acceptance**  
- **Given** claimed GPS ≠ EXIF GPS (opt-in retain path)  
- **When** FlagEngine runs  
- **Then** a warn (or configured) flag is raised

### SEC-003 — Photo PII handling
Treat photos as personal data (faces, plates, homes). No public gallery of others’ packets in hackathon demo.

**Acceptance**  
- **Given** packet A belonging to user/session A  
- **When** unauthenticated listing of all packets is requested  
- **Then** listing is denied or empty (opaque id direct access only as designed)

### SEC-004 — Opaque IDs & packet access
Packet access by opaque id; no sequential scraping surface. Optional simple curator token for `/review` — no over-engineered SSO required for hackathon.

**Acceptance**  
- **Given** valid curator token (if enabled) vs absent token  
- **When** `/review` is accessed  
- **Then** authorized access succeeds; unauthorized fails closed

### SEC-005 — AI data flow disclosure
If cloud VLM is used: do not send exact home GPS; disclose AI data flow in README.

**Acceptance**  
- **Given** cloud AI enabled  
- **When** request payload to provider is built  
- **Then** precise home coordinates are absent; README contains disclosure section

### SEC-006 — Secrets
No API keys or secrets in git. Local `.env` only.

**Acceptance**  
- **Given** repository scan of tracked files  
- **When** CI/secret check runs (manual acceptable for hackathon)  
- **Then** no live keys committed

### SEC-007 — Retention / cleanup
Document wipe of uploads after judging; implement cleanup script or ops checklist.

**Acceptance**  
- **Given** post-judging cleanup procedure  
- **When** executed in staging  
- **Then** uploaded media and packet stores for demo are removable without orphaned public URLs

### SEC-008 — Non-claim UI copy
UI shall forbid medical diagnosis / outbreak claims from CS visits.

**Acceptance**  
- **Given** citizen confirm and FHIR views  
- **When** copy is reviewed  
- **Then** non-claim language is present; no “diagnosed”/“outbreak confirmed” strings in product templates

---

## 9. Non-functional requirements

### NFR-001 — Reliability without AI
Core integrity path shall function with `NullAiAssist` and no external AI network dependency.

### NFR-002 — Maintainability
Modular monolith packages (`domain`, `flags`, `ai`, `fhir`, `provenance`, `web`, plus Phase 4 `application` + `persistence`) with typed ports; thin `app/main.py`.

### NFR-003 — Testability
Flag rules, state machine, mapper, provenance, and AI port shall be unit-testable without browser. Golden fixtures under `tests/fixtures/`.

### NFR-004 — Extensibility
`IgValidatorPort` and alternate `AiAssistPort` implementations shall be addable without rewriting export gates.

### NFR-005 — Observability
Structured logs or equivalent for refuse reasons, state transitions, and export failures (hackathon-light OK).

### NFR-006 — Security baseline
Meet SEC-* for demo; production GDPR role of OAH cities remains **[UNKNOWN]** / out of hackathon legal scope.

### NFR-007 — Performance (hackathon-reasonable)
Single-user demo path (upload → confirm → export) completes in interactive time on modest hosting (order of seconds, not minutes). **Production-scale CS throughput is future** — not a hackathon acceptance gate.

### NFR-008 — Feasibility posture
No microservices, Kubernetes, blockchain, or multi-agent runtime required for MVP.

---

## 10. Traceability

| Requirement | Product area | Architecture component | Future phase | Test type |
|---|---|---|---|---|
| FR-001–004 | Submission / sites / media | `domain`, `web` ingest | 2, 6 | Unit + API |
| FR-010–013 | Flags | `flags` FlagEngine | 3 | Unit + fixtures |
| FR-020–031 | Workflow | `domain` state machine | 2 | Unit (illegal transitions) |
| HITL-001–005 | Confirm / review | `domain`, `web` | 6, 7 | Unit + API/UI script |
| FHIR-001–009 | FHIR export | `fhir` mapper, StructuralGuard, exporter | 5 | Unit + golden Bundle |
| AI-001–006 | Optional AI | `ai` AiAssistPort | **[IMPLEMENTED Phase 8]** | Null + Fake + provider adapter (offline suite) |
| PROV-001–002 | Provenance / audit | `provenance` | 4 | Unit + fixture journeys |
| SEC-001–008 | Privacy / access | media pipeline, `web`, config | 9 | Unit + manual checklist |
| NFR-001–008 | Cross-cutting | monolith | 10 | CI pytest + deploy smoke |

**Phase 1 already:** AI-001, FHIR-003, FHIR-002 safety (no preliminary path) — keep regressions green.

---

## 11. Phase mapping (Phases 2–10)

Do not start a phase until the previous is approved/landed unless the human explicitly parallelizes.

| Phase | Focus | Primary requirement IDs | Exit sketch |
|---|---|---|---|
| **1** (done scaffold) | Packages, Null AI, export refuse | AI-001, FHIR-003, FHIR-002 partial | **[IMPLEMENTED Phase 1]** |
| **2 — Domain** | Real `ObservationPacket` mutators + illegal-transition tests | FR-020–031, FR-001–002 (typed fields), HITL-001/003 | State machine tests green |
| **3 — Flags** | Modular rules + severities + revalidate | FR-010–013, HITL-003–004 | Rule fixtures green |
| **4 — Persistence + Provenance** | Durable store + append-only log answering audit Qs | PROV-001–002, FR-004 | **[IMPLEMENTED Phase 4]** `docs/PERSISTENCE.md`; audit helper + pytest |
| **5 — FHIR** | Mapper + StructuralGuard + export digest | FHIR-001–009 (007 = internal audit) | **[IMPLEMENTED Phase 5]** — see `docs/FHIR-SPEC.md` |
| **6 — Citizen UX** | `/upload` → flags → confirm → `/fhir` after finalize | FR-002–003, HITL-002, SEC-008 | 90s path manual + smoke |
| **7 — Reviewer** | `/review` desk | FR-025, FR-027, HITL-005, SEC-004 | Review fixture path |
| **8 — AI** | Optional non-null provider behind port | AI-002–006 (AI-001 remains) | **[IMPLEMENTED Phase 8]** Null + Fake + provider adapter; see `docs/AI-POLICY.md` |
| **9 — Security** | EXIF, PII, retention, disclosures | SEC-001–007 | Checklist + EXIF unit |
| **10 — Deploy / E2E** | Public URL, demo script, CI, judging uptime | NFR-001–007, success criteria in PRD | Deployed demo + video checklist |

---

## Open Questions

1. Finalize trigger: auto-after-confirm vs explicit export button — **Resolved Phase 6:** explicit Confirm and explicit Finalize remain separate (see `docs/UX-SPEC.md`). One-click confirm+export rejected.  
2. Which completeness fields are `hard_reject` vs `soft_block_finalize` for MVP — **[VERIFY]** Annex I (Phase 3 FlagEngine).  
3. Exact TemporaryOahSystem codes and `ObservationWithCompOah` slice requirements for macrophytes/riparian — **[VERIFY]** IG. Phase 2 uses abstract citizen-safe keys only.  
4. Performer representation for hackathon (PractitionerRole-lite vs Organization display) — **[VERIFY]** / spike allows lite.  
5. Reviewer authentication strength for public demo vs private token — **Resolved Phase 7 (interim):** auth **not implemented**; demo reviewer Actor at composition root; disclosed in HITL-POLICY + UI footer. Real auth deferred.  

### Phase 6 decisions (landed)

| Topic | Decision |
|---|---|
| Citizen confirm surface | `/observation/{packet_id}` (not reviewer desk) |
| `/review` | Phase 7 stub; `?packet_id=` redirects to observation |
| FlagEngine in demo | `DeterministicFlagEngine` via composition → `ObservationService` |
| Soft blocks in UX | Needs correction group; confirm disabled until cleared |
| FHIR result honesty | `NullFhirValidator` → validation status `not_run`; structural profiles only |

### Phase 7 decisions (landed)

| Topic | Decision |
|---|---|
| Reviewer service | `ReviewerFlowService` separate from `CitizenFlowService` |
| Queue | `list_for_review` — `NEEDS_REVIEW` only; oldest `created_at` first |
| Accept | `NEEDS_REVIEW` → `CONFIRMED`; does **not** finalize or export FHIR |
| Reject | Structured `reason_code` set in `docs/HITL-POLICY.md`; empty refused |
| Edit | Reviewer mutators + FlagEngine revalidate; stay `NEEDS_REVIEW` |
| Soft-block | Does not auto-escalate; does not equal REJECTED |
| Auth | Not implemented (demo Actor); see HITL-POLICY |

### Phase 8 decisions (landed)

| Topic | Decision |
|---|---|
| Default provider | `NullAiAssist` (`AI_PROVIDER=null`) — no network |
| Non-null providers | `FakeAiAssist` (offline) + `OptionalProviderAiAssist` (HTTP when keyed) |
| Capabilities | Constrained categorical suggestions + optional flag explain |
| Human gate | Explicit Use suggestion / Keep my value before field mutation |
| Photo AI | Deferred — no fake image analysis |
| Policy doc | `docs/AI-POLICY.md` |

---

*End of REQUIREMENTS — Phase 8 optional AI landed; Phase 9 security next.*
