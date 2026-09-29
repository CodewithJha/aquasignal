# Phase 1 Audit — ConfirmGate vs StreamWitness Scaffold

**Date:** 21 Sep 2026  
**Scope:** Audit only. **No product code modified.**  
**Source of truth:** `docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md`  
**Priors challenged:** `AGENTS.md`, `README.md`, `docs/WIN-PLAN.md`, `docs/SUBMISSION.md`, scaffold under `app/`  

---

## A. Repository inventory

### Key paths (product-relevant; `.venv` ignored)

| Path | Role |
|---|---|
| `app/main.py` | Entire FastAPI app: routes, draft placeholder, FHIR bundle builder, in-memory sessions |
| `app/__init__.py` | Empty package marker |
| `app/templates/{base,upload,review}.html` | Server-rendered UI |
| `app/static/style.css` | Minimal styles |
| `app/data/cities.json` | Five OAH cities seed |
| `app/data/sample_fhir_location.json` | Placeholder Location JSON |
| `app/data/sample_fhir_observation.json` | Placeholder Observation with `status: preliminary` |
| `requirements.txt` | fastapi, uvicorn, python-multipart, jinja2, pydantic |
| `.env.example` | Commented `OPENAI_API_KEY` / `VISION_MODEL` stubs |
| `docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md` | **Architecture authority (BUILD ConfirmGate)** |
| `docs/PRODUCT-VALIDATION.md` | Domain/FHIR hostile validation |
| `docs/RESEARCH-HACKATHON-OPPORTUNITY.md` | Opportunity research (pre-ConfirmGate) |
| `docs/WIN-PLAN.md` / `docs/SUBMISSION.md` | StreamWitness thesis (superseded by spike) |
| `AGENTS.md` / `README.md` | Still branded StreamWitness + factsheet checklist |
| `tests/` | **Does not exist** |
| `pyproject.toml` / `package.json` | **Absent** |

### Stack (facts)

- Python + FastAPI + Jinja2 SSR + Pydantic listed in requirements (Pydantic unused in `main.py`).
- Single process; no DB; `SESSIONS: dict` in memory.
- No Pillow, no pytest, no SQLite, no AI SDK wired.
- No modular packages: no `domain/`, `flags/`, `fhir/`, `ai/`, `provenance/`, `web/`.

### What the scaffold currently does (facts)

1. **GET `/` and `/upload`** — form: city select + optional photo + free-text fields: habitat, macroinvertebrates, diptera_mosquitoes, water_quality, well_being (`upload.html`, `main.py` upload handler).
2. **POST `/upload`** — validates city ∈ five OAH ids; creates session UUID; calls `draft_from_checklist` (echoes form into DRAFT indicators; no vision); stores in `SESSIONS`; renders review.
3. **GET/POST `/review`** — edit indicators + One Health sentence; actions `confirm` / `reject` / edit; appends thin audit list; sets `confirmed` bool.
4. **GET/POST `/fhir`** — returns Bundle of Location + Observation copied from samples; **`observation["status"] = "final" if confirmed else "preliminary"`** (`main.py` L72); free-text component codes; no performer; subject is display-only; no Provenance; **serves FHIR for unconfirmed sessions**.
5. Photo filename may be recorded; **bytes are not persisted**; no EXIF scrub; photo optional.
6. Branding: **StreamWitness** everywhere (templates, FastAPI title, README, AGENTS).

---

## B. Architecture spike vs scaffold matrix

| Spike requirement | Current state | Gap | Severity |
|---|---|---|---|
| **Product thesis = ConfirmGate** (integrity lifecycle, not vision scorer) | Product named StreamWitness; copy sells “factsheet check” + vision/LLM draft | Rename + re-scope copy/docs/UI; kill StreamWitness-as-thesis | **blocker** |
| **Domain model** (`SiteRef`, `MediaAsset`, `ObservationPacket`, `FieldValue`, `QualityFlag`, `ProvenanceEvent`, `FhirExport`) | Ad-hoc `SESSIONS` dict with flat free-text fields | No typed entities; wrong fields | **blocker** |
| **State machine** `RECEIVED→FLAGGED→…→FINALIZED`; app state ≠ FHIR status | Boolean `confirmed` only; FHIR emitted anytime | No workflow states; FHIR tied to confirm via `preliminary`/`final` | **blocker** |
| **Flag engine** (modular rules, severities, no composite score) | Absent | Entire module missing | **blocker** |
| **Citizen-safe Annex I fields** (macrophytes A/P/E, riparian bins, hydromorph P/E/A, foam/colour/smell) | Free-text habitat / macros / Diptera / WQ / well-being | Wrong domain; invites lab/AI overclaim | **blocker** |
| **AI: `AiAssistPort` + `NullAiAssist` required** | `draft_from_checklist` hard-coded in `main.py`; no port | No null-provider contract; draft is form echo labeled “model” | **major** |
| **AI never authority; suggestions ≠ FHIR without confirm** | Confirm gate exists for `confirmed` flag, but FHIR still emitted pre-confirm as preliminary | Partial HITL; export gate incomplete | **blocker** |
| **FHIR only after finalize; always `status=final`** | Emits preliminary when unconfirmed; sample file is preliminary | Violates OAH ObservationIndicatorsOah pattern if claimed as OAH | **blocker** |
| **Profiles: LocationOah + ObservationIndicatorsOah / ObservationWithCompOah + Provenance** | Generic Location/Observation; free-text codes; no meta.profile; no Provenance | Non-conformant placeholder | **blocker** |
| **TemporaryOahSystem codes; no fake codes** | `code: {"text": key}` for invented keys | Fake vocabulary | **blocker** |
| **performer 1.., subject→Location, identifier on Location** | Missing performer; subject display only; Location has no required identifier system | Structural gaps | **blocker** |
| **Append-only provenance answering 7 HITL audit questions** | Mutable `audit[]` list of strings; no hashes/diffs/model versions | Cannot prove AI≠human or export hash | **major** |
| **UX: `/upload` → flags → confirm → `/fhir` only after confirm; `/review` = reviewer desk** | `/review` is citizen confirm (not reviewer queue); `/fhir` works unconfirmed | Route semantics wrong; no flag panel | **major** |
| **Privacy: EXIF strip, opaque ids, no public listing** | UUID ids OK; photo not stored; no EXIF path | EXIF policy unimplemented when media lands | **minor** (Phase 1) / **major** when media lands |
| **Modular monolith packages** | Monolith file `main.py` only | Must split packages | **major** |
| **Tests: flags/state/mapper/provenance/AI-port + fixtures** | No `tests/` | Zero coverage | **blocker** for Phase 1 exit if scaffolding claims readiness |
| **Five cities only** | `cities.json` correct five | Retain | — (ok) |
| **One Health sentence template (cited, non-diagnostic)** | Free-form editable placeholder sentence | Needs citation template later | **minor** (Phase 1) |
| **No trust score / multi-agent / blockchain / microservices / full FHIR server** | None of these present | Do not introduce | watchlist |
| **Pillow / SQLite or JSON persistence** | Neither | Add when implementing media/store (not necessarily all of Phase 1) | **major** (later phases) |

---

## C. Contradictions (explicit list)

1. **FHIR `preliminary` anti-pattern (kill criterion #5)**  
   - Evidence: `app/main.py` L72: `observation["status"] = "final" if confirmed else "preliminary"`.  
   - Evidence: `app/data/sample_fhir_observation.json` L4: `"status": "preliminary"`.  
   - Evidence: `app/templates/review.html` L26: “Not confirmed — FHIR stays preliminary.”  
   - Spike: OAH profiles require `status=#final`; drafts must not be OAH-profiled Observations.

2. **FHIR export without human authority (kill criterion #2 risk)**  
   - Evidence: `fhir_get` / `fhir_bundle` return Bundle for any session, including `confirmed: False`.  
   - Spike: exporter must refuse until `FINALIZED` / confirmed finalize.

3. **StreamWitness-as-thesis vs ConfirmGate BUILD decision**  
   - Evidence: `README.md`, `AGENTS.md`, `docs/WIN-PLAN.md`, FastAPI `title="StreamWitness"`, `base.html` H1.  
   - Spike final decision: BUILD **ConfirmGate**; StreamWitness vision-scoring path is kill/reject alternative.

4. **Wrong indicator model (factsheet checklist vs Annex I)**  
   - Evidence: `upload.html` + `draft_from_checklist` indicators: habitat, macroinvertebrates, diptera_mosquitoes, water_quality, well_being.  
   - Spike/validation: those are not citizen-safe Annex I / TemporaryOahSystem primary set; Diptera traps and well-being epi are excluded from citizen AI draft.

5. **Invented free-text FHIR codes (kill criterion #4)**  
   - Evidence: `fhir_bundle` builds `component` with `{"code": {"text": key}, "valueString": ...}` for the five free-text keys.  
   - Spike: TemporaryOahSystem codes only (e.g. `#foam`, `#riparianVegetation`).

6. **AI framed as drafting ecological checklist from photo**  
   - Evidence: README L5 “vision/LLM draft”; upload copy “The model will draft”; `draft_from_checklist` docstring “Placeholder vision/LLM”.  
   - Spike: AI optional behind port; Null required; no photo→BMWP/pathogen/Diptera/disease.

7. **Missing flag engine / hard gates**  
   - Evidence: no flags in session; confirm always allowed regardless of photo quality or vocabulary.  
   - Spike: hard flags block confirm/finalize.

8. **App workflow conflated with FHIR Observation.status**  
   - Evidence: confirm flips FHIR status preliminary→final rather than creating FHIR only at finalize.  
   - Spike Part 5 invariant: domain state ≠ FHIR status; FHIR exists only at FINALIZED as final.

9. **`/review` is citizen HITL, not reviewer desk**  
   - Evidence: `review.html` edits citizen draft; no `NEEDS_REVIEW` queue.  
   - Spike: primary confirm on citizen path; `/review` = secondary reviewer desk.

10. **AGENTS.md / WIN-PLAN still mandate StreamWitness factsheet flow**  
    - Evidence: `AGENTS.md` L17–25; `WIN-PLAN.md` L61–69.  
    - Spike: priors challenged; WIN-PLAN to be updated after approval.

11. **LocationOah / performer gaps**  
    - Evidence: sample Location lacks OAH `identifier` 1..; Observation has no `performer`.  
    - Spike Part 9: both required for profiled Observations.

12. **No composite trust score in code (good)** — but docs priors historically floated trust products; ensure Phase 1 does not add one. Scaffold does **not** currently implement trust scores, blockchain, multi-agent, microservices, or full FHIR server.

---

## D. Retain / Replace / Delete

| Path | Recommendation | Why |
|---|---|---|
| `app/data/cities.json` | **Retain** | Correct five cities; becomes `SiteRef` seed input |
| FastAPI + Jinja2 + `requirements.txt` baseline | **Retain** (extend) | Matches spike stack |
| `.gitignore` / `.env.example` | **Retain** (tighten later) | Secrets hygiene OK |
| `docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md` | **Retain** | Source of truth |
| `docs/PRODUCT-VALIDATION.md` | **Retain** | Domain evidence |
| `docs/RESEARCH-HACKATHON-OPPORTUNITY.md` | **Retain** | Context; do not treat as product spec |
| `docs/PHASE1-AUDIT.md` | **Retain** | This audit |
| `app/main.py` monolith domain/FHIR logic | **Replace** | Move behavior into modular packages; thin web entrypoint |
| `app/data/sample_fhir_*.json` | **Replace** | Remove preliminary sample; replace with golden fixtures under `tests/fixtures/` aligned to TemporaryOahSystem + status=final only |
| `app/templates/upload.html` | **Replace** | Annex I enums + flag-ready form; ConfirmGate copy |
| `app/templates/review.html` | **Replace / split** | Citizen confirm surface ≠ reviewer desk; kill “preliminary” copy |
| `app/templates/base.html` | **Replace** branding | ConfirmGate name; keep Track 3 + OAH links |
| `app/static/style.css` | **Retain lightly** | Restyle later; not architecture |
| `README.md` | **Replace** content | ConfirmGate thesis, HITL, final-only FHIR, AI disclosure |
| `AGENTS.md` | **Replace** product sections | Agents must not reintroduce StreamWitness checklist |
| `docs/WIN-PLAN.md` | **Replace** after approval | Spike says update indicators/thesis |
| `docs/SUBMISSION.md` | **Replace** product bullets | Align checklist to ConfirmGate |
| StreamWitness product thesis as hero | **Delete** | Per spike BUILD ConfirmGate |
| In-memory-only as long-term store design | **Replace** | Spike: JSON/SQLite + provenance jsonl |
| `draft_from_checklist` as AI | **Delete/replace** | Become `NullAiAssist` + optional later |
| FHIR preliminary path | **Delete** | Kill criterion |
| Free-text lab-ish fields | **Delete** from citizen form | Replace with Annex I allowlist |

---

## E. Phase 1 plan (architecture cleanup ONLY)

### Phase 1 will

1. Establish modular monolith package layout per spike Part 16/19: `app/domain`, `app/flags`, `app/ai`, `app/fhir`, `app/provenance`, `app/web` (thin routes/templates).
2. Introduce stub domain types and workflow state enum **without** full transition implementation (skeletons + invariants documented in code comments / empty modules with typed placeholders).
3. Kill preliminary FHIR pattern: exporter stub that **refuses** unconfirmed packets; no OAH-shaped Observation with `status=preliminary` in samples or UI copy.
4. Rebrand user-facing product to **ConfirmGate** in templates/README entry points (docs that still say StreamWitness get a clear “superseded” note or update).
5. Add `NullAiAssist` implementing `AiAssistPort` interface; wire web so demo path does not require an API key.
6. Add empty/stub flag engine module with rule-id registry shape (no full rule logic yet, or one trivial completeness stub if needed for structure only).
7. Create `tests/` skeleton + at least one failing-or-passing contract test that **exporter refuses unconfirmed** and that Null AI is importable.
8. Keep five-city seed; do not invent cities.
9. Leave full Annex I UI, full state machine, real media/EXIF, reviewer queue, and IG mapper implementation for later phases.

### Phase 1 will NOT

- Ship a complete ConfirmGate MVP or 90s demo path.
- Implement photo→ecology, trust scores, multi-agent, blockchain, CS/DSS/DipteraCAST replacement.
- Implement full FlagEngine rules, full state machine transitions, or production persistence.
- Claim IG validator green or full TemporaryOahSystem coverage.
- Rewrite research docs into ADRs / architecture.md sprawl.
- Start Phase 2 domain+state machine beyond scaffolding hooks.

---

## F. First concrete changes (ordered checklist)

1. **Create package tree** under `app/`: `domain/`, `flags/`, `ai/`, `fhir/`, `provenance/`, `web/` with `__init__.py` files.
2. **Move** route handlers from `app/main.py` → `app/web/routes.py` (or similar); leave `app/main.py` as FastAPI app factory mounting static/templates only.
3. **Add** `app/domain/models.py` stubs: `SiteRef`, `ObservationPacket`, `WorkflowState` enum matching spike names; stop using free-form `SESSIONS` shape as the long-term model (compat shim OK temporarily).
4. **Add** `app/ai/port.py` + `app/ai/null.py` (`NullAiAssist`); **delete/replace** `draft_from_checklist` vision framing.
5. **Add** `app/fhir/exporter.py` stub: `export_bundle(packet)` raises/returns error if not confirmed/finalized; **never** sets `preliminary`.
6. **Replace** `app/data/sample_fhir_observation.json` — either remove from runtime path or rewrite as **non-exported** fixture note; do not serve preliminary as OAH sample on `/fhir`.
7. **Update** `base.html` / README product name → ConfirmGate; remove “FHIR stays preliminary” from `review.html`.
8. **Add** `app/flags/engine.py` stub + `app/provenance/log.py` stub (append-only interface).
9. **Create** `tests/test_fhir_export_refuses_unconfirmed.py` (+ `tests/fixtures/` placeholder).
10. **Extend** `requirements.txt` with `pytest` (and later Pillow when media lands — optional in Phase 1).
11. **Mark** `AGENTS.md` / `WIN-PLAN.md` for follow-up rewrite (Phase 1 may add a one-line supersession pointer to ConfirmGate spike — full rewrite can be same PR as branding).
12. **Do not** add trust score, AI provider SDK, or Annex I full forms in this phase unless needed for compile/import smoke.

---

## G. Phase 1 acceptance criteria

Phase 1 is done when **all** of the following are true:

- [ ] Package layout exists: `domain`, `flags`, `ai`, `fhir`, `provenance`, `web` importable.
- [ ] `NullAiAssist` implements documented `AiAssistPort`; core import/demo path works with no API keys.
- [ ] No runtime path emits `Observation.status = "preliminary"` for app-generated Bundles.
- [ ] Exporter (stub or real) **refuses** unconfirmed/non-finalized packets (test asserts refusal).
- [ ] User-facing brand on primary templates is **ConfirmGate** (not StreamWitness-as-thesis).
- [ ] Five cities still only Coimbra, Benevento, Ghent, Oslo, Toulouse.
- [ ] No composite trust score, multi-agent runtime, blockchain, or photo→BMWP/pathogen code introduced.
- [ ] `pytest` runs at least the refusal + Null AI smoke tests green.
- [ ] `AGENTS.md` or README no longer instructs agents to build the factsheet habitat/macros/Diptera/WQ/well-being StreamWitness checklist as the product core (points to ConfirmGate spike).
- [ ] Kill-criteria §17 of spike still satisfied by absence (not violated by new code).

---

## H. Risks & kill-criteria watchlist

| Risk during Phase 1 | Kill criterion touched | Mitigation |
|---|---|---|
| Leaving preliminary in samples “for draft UX” | #5 | Delete/refuse; use domain states only |
| Half-migrating modules but keeping `fhir_bundle` preliminary branch | #2/#5 | Single exporter entrypoint; delete old function |
| Renaming to ConfirmGate but keeping macro/Diptera free-text form as “temporary” | #1/#4 drift | Stub fields or empty form; do not deepen wrong model |
| Adding OpenAI “just to show AI” required for tests | #8 | Null path mandatory in CI |
| Inventing temporary trust % in UI badge | #3 | Flags only / “DRAFT” label without score |
| Claiming `meta.profile` ObservationIndicatorsOah while still free-text | #4 | Do not claim profiles until mapper uses TemporaryOahSystem |
| Expanding Phase 1 into full MVP | Feasibility / scope kill | Stick to scaffolding acceptance above |
---

## I. Recommended next phase after Phase 1

**Phase 2:** Implement the real domain `ObservationPacket` + workflow state machine (`RECEIVED`→`FLAGGED`→`AWAITING_CONFIRM`→`CONFIRMED`→`FINALIZED`) with illegal-transition tests — do not start until Phase 1 is approved and landed.

---

**PHASE 1 AUDIT COMPLETE — AWAITING APPROVAL TO MODIFY CODE**
