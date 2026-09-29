# ConfirmGate — Domain Model (Phase 2 + Phase 7 review notes)

Status: ACTIVE (Phase 7)  
Authority: `docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md`  
Date: 21 Sep 2026  

App workflow state ≠ FHIR `Observation.status`. FHIR exists only after `FINALIZED`, always `final`.

---

## Aggregate

**`ObservationPacket`** — natural aggregate root for one citizen visit.

Owns: `SiteRef` (embedded snapshot), `FieldValue` map, suggestions (non-authoritative), `QualityFlag` list, `WorkflowState`, optional `ConfirmationSnapshot`, provenance intents buffer, optional One Health sentence / fhir_bundle_id after finalize.

Identity: opaque `packet_id` (UUID hex).

---

## Value objects / enums

| Type | Role |
|---|---|
| `SiteRef` | Seeded site; `city` ∈ `OAH_CITIES` (single source in `app/domain/cities.py`) |
| `FieldValue` | Protocol-lite datum; code ∈ citizen-safe allowlist; excluded codes refused |
| `QualityFlag` | Structured fitness signal; severity only — **no trust score** |
| `ConfirmationSnapshot` | Frozen fields + deterministic SHA-256 content hash |
| `Actor` | `citizen` / `reviewer` / `system` / `ai_provider` |
| `ProvenanceIntent` | Append-oriented audit record emitted by mutators (no durable store in domain) |
| `WorkflowState` | Lifecycle enum; terminals: `FINALIZED`, `REJECTED`, `WITHDRAWN` |
| `Severity` | `hard_reject` \| `soft_block_finalize` \| `warn` |

Exact TemporaryOahSystem bindings for export are documented in **`docs/FHIR-SPEC.md`** (Phase 5). Domain storage still uses abstract citizen-safe keys (`foam`, `macrophytes`, …); the FHIR adapter owns system URIs and coding.

---

## State transition matrix

| Source | Target | Allowed? | Preconditions |
|---|---|---|---|
| (create) | RECEIVED | Yes | Valid `SiteRef` (five cities) |
| RECEIVED | FLAGGED | Yes | `apply_flags` by system/reviewer |
| FLAGGED | FLAGGED | Yes (re-eval) | `apply_flags` replaces flags |
| FLAGGED | AWAITING_CONFIRM | Yes | No standing non-overridden `hard_reject` |
| FLAGGED | NEEDS_REVIEW | Yes | Escalation (`request_review`) |
| FLAGGED | REJECTED | Yes | System/reviewer + reason |
| AWAITING_CONFIRM | CONFIRMED | Yes | Author citizen; no standing hard_reject; snapshot frozen |
| NEEDS_REVIEW | CONFIRMED | Yes | Reviewer `accept_review`; no standing hard_reject |
| NEEDS_REVIEW | REJECTED | Yes | Reviewer + reason |
| CONFIRMED | FINALIZED | Yes | Valid confirmation snapshot; hash matches fields; no standing soft_block/hard |
| *non-terminal* | WITHDRAWN | Yes | Author citizen |
| RECEIVED | FINALIZED | **No** | — |
| REJECTED / WITHDRAWN / FINALIZED | * | **No** | Terminal |
| CONFIRMED | AWAITING_CONFIRM | **No** | Unconfirm not in Phase 2 matrix |
| CONFIRMED | NEEDS_REVIEW | **No** | Not in user-specified matrix |
| AWAITING_CONFIRM | REJECTED | **No** | Reject only from FLAGGED \| NEEDS_REVIEW |

Happy path: `RECEIVED → FLAGGED → AWAITING_CONFIRM → CONFIRMED → FINALIZED`.

---

## Invariants

1. Illegal transitions raise `InvalidStateTransition` (current / requested / reason) — no HTTP codes in domain.  
2. Standing `hard_reject` blocks `mark_awaiting_confirm` / `confirm` / `accept_review`.  
3. `warn` alone does not block confirm.  
4. Standing `soft_block_finalize` blocks finalize (not confirm).  
5. Confirmed fields cannot silently mutate; no public mutable field/flag lists.  
6. Finalize requires confirmation snapshot whose hash matches current fields.  
7. AI (`ai_provider`) cannot confirm, accept_review, reject, withdraw, or finalize.  
8. Terminals refuse further mutators that would change authority state.  
9. Suggestions never copy into `fields` or FHIR without human field write + confirm.

---

## Mutation API (controlled)

`create`, `rehydrate` (persistence only; no provenance emit), `set_field` / `replace_fields`, `apply_suggestions`, `apply_flags`, `mark_awaiting_confirm`, `request_review`, `override_flag`, `confirm`, `accept_review`, `reject`, `withdraw`, `finalize`.

---

## Provenance boundary

Domain emits `ProvenanceIntent` records (buffered + optional `ProvenanceSink`).  
`drain_provenance_intents()` hands them to Phase 4 persistence. Domain does **not** import `app.provenance`, FastAPI, FHIR, or AI SDKs.

Enough structure for HITL audit questions once stored: actor, action, before/after, model_id, rule_engine_version, confirmation hash on confirm/export.

---

## Extension points (later phases)

| Phase | Extension |
|---|---|
| 3 | FlagEngine rules populate `QualityFlag` via `apply_flags` — **[IMPLEMENTED Phase 3]** `app/flags` + `docs/FLAG-ENGINE.md` |
| 4 | Durable packet store + append-only log from intents — **[IMPLEMENTED Phase 4]** `app/application` + `app/persistence` + `docs/PERSISTENCE.md` |
| 5 | FHIR mapper reads FINALIZED packet + snapshot only — **[IMPLEMENTED Phase 5]** |
| 6–7 | Web UX; reviewer desk — **[IMPLEMENTED Phase 6–7]** |
| 8 | Non-null `AiAssistPort` → `apply_suggestions` only; human accept → `set_field` + FlagEngine | **[IMPLEMENTED Phase 8]** |

### Phase 4 persistence notes

- `ObservationPacket.rehydrate(...)` rebuilds aggregates without emitting provenance.
- `rule_engine_version` is readable; stored flags are a snapshot keyed by that version.
- Durable provenance is outside the domain (`drain_provenance_intents` → application UnitOfWork).
- Optimistic concurrency `revision` lives on `PacketRecord` (application), not as a domain mutator.

### Phase 7 domain notes

- `RejectionReasonCode` / `REJECTION_REASON_CODES` — structured reject reasons (ops codes, not OAH FHIR).
- Field edits allowed in `NEEDS_REVIEW` for **reviewer** actors only; `apply_flags` may revalidate while staying `NEEDS_REVIEW`.
- `reject(..., reason_code=, explanation=)` — empty/unknown codes refused; desk reject emits `review.rejected`.
- Accept → `CONFIRMED` only; finalize remains a separate mutator.

---

## Phase 2 assumptions (documented)

1. **Finalize is explicit** (`finalize` mutator), not auto-after-confirm.  
2. **No unconfirm** transition (REQUIREMENTS FR-031 deferred; not in exact matrix).  
3. **Field edits** in `RECEIVED` / `FLAGGED` (any non-AI authority actor) and `NEEDS_REVIEW` (**reviewer only**; Phase 7).  
4. **Citizen-safe codes** are abstract allowlist keys until IG binding verified.

---

## AquaSignal Phase A1 (domain contracts only)

Authority for product thesis: `docs/AQUASIGNAL-ARCHITECTURE-SPIKE.md` (BUILD WITH CHANGES — Site Investigation Brief). ConfirmGate `ObservationPacket` remains unchanged and first-class.

| Package | Types |
|---|---|
| `app/domain/evidence` | `EvidenceItem`, `EvidenceSnapshot`, `EvidenceRelation`, `EvidenceSourceClass`, `RelationType` |
| `app/domain/signal` | `EnvironmentalSignal`, `SignalType`, `TimeWindow`, `DetectorId`, `DetectorVersion`, `EvidenceSnapshotRef` |
| `app/domain/investigation` | `InvestigationCase`, `AnalysisRun`, `HumanDecision`, `CaseState`, `AnalysisRunStatus`, `DecisionCode` |

Reused as-is: `SiteRef`, `Actor` / `ActorType`.  
Adapted: `InvalidStateTransition` accepts any status `Enum` (case/run as well as packet).

Invariants (A1): signals are hypotheses not diagnoses; case close/dismiss requires `HumanDecision`; AI cannot create authoritative decisions; `AnalysisRun` immutable after `SUCCEEDED`; illegal transitions raise `InvalidStateTransition`. No detector math, persistence, UI, FHIR, or AI in A1.

### Phase A3 (Signal Engine)

Pure detectors live in **`app/signals/`** (not domain). Contract: `EvidenceObservation` + `AnalysisContext` → `SignalResult` via versioned `SignalDetector`s. See `docs/SIGNAL-ENGINE.md`. Detectors must not call persistence or enforce ConfirmGate FINALIZED (A4).

### Phase A4 (application orchestration)

- **Eligibility:** only `WorkflowState.FINALIZED` ConfirmGate packets, plus labelled fixtures (`source_class=fixture`, `is_synthetic=True`). Drafts raise `EvidenceNotEligible` in application (not UI).
- **Services:** `AnalysisService` coordinates snapshot → `SignalEngine` → domain mapping → A2 repos in one UoW. `InvestigationService.open_case` is optional and separate (no UI).
- **Mapping:** `SignalResult` with a `signal_type` → `EnvironmentalSignal`; all `RelationResult`s → `EvidenceRelation` (application assigns ids). `NO_SIGNAL` results are not persisted as signals.
- **Repro:** `AnalysisRun.parameters_hash` = SHA-256 of canonical params; `detector_set_version` from registry; each analyze creates a new run (append-only; never overwrite SUCCEEDED).
- **Provenance:** `analysis.snapshot_built` / `analysis.run_succeeded` appended onto ConfirmGate packet ids only (FK-safe). Fixture-only runs skip packet provenance.

### Phase A5 (investigation web + brief retrieval)

- **Read model:** `InvestigationBriefService` assembles typed list/detail DTOs from persisted A4 runs only — no SignalEngine re-run, no SQL in application/web.
- **Surfaces:** `/investigate`, `/investigate/sites/{site_id}`, `/investigate/analyses/{run_id}` plus typed `/api/...` endpoints.
- **Demo seed:** `python scripts/seed_aquasignal_demo.py` (A3 fixtures + A4 analyze). See `docs/DEMO.md`.
