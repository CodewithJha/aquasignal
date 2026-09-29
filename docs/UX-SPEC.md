# ConfirmGate — UX Specification (Phase 6–7)

Status: ACTIVE (Phase 7)  
Date: 21 Sep 2026  
Authority: `docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md`, `docs/PRD.md`, `docs/REQUIREMENTS.md`, `docs/HITL-POLICY.md`

## 1. Journey (citizen, ~90s demo)

```text
Submit (/upload)
  → DeterministicFlagEngine evaluation (FLAGGED)
  → Correct + revalidate (same packet_id)
  → Explicit Confirm (CONFIRMED)     ≠ finalize
  → Explicit Finalize (FINALIZED)   ≠ auto-export
  → FHIR result (/fhir?packet_id=…) + Bundle JSON
```

Optional branch: FLAGGED → Send to reviewer → `/review/{id}` (NEEDS_REVIEW).

AI (`NullAiAssist` by default; optional Fake/HTTP providers) may attach advisory suggestions; never required; never authoritative. Explicit **Use suggestion** / **Keep my value** before any field mutation.

## 2. Screens & routes

| Screen | Route | Method | Purpose |
|---|---|---|---|
| Submit | `/`, `/upload` | GET | Protocol-lite form (five OAH sites) |
| Submit | `/upload` | POST | Create packet, run FlagEngine, redirect |
| Observation | `/observation/{id}` | GET | Flags, correct, confirm, finalize |
| Correct | `/observation/{id}/correct` | POST | Replace fields + revalidate |
| Use suggestion | `/observation/{id}/suggestion/accept` | POST | Human copies AI advisory → field + FlagEngine |
| Keep my value | `/observation/{id}/suggestion/decline` | POST | Clear advisory; fields unchanged |
| Confirm | `/observation/{id}/confirm` | POST | Human authority snapshot |
| Request review | `/observation/{id}/request-review` | POST | FLAGGED → NEEDS_REVIEW |
| Finalize | `/observation/{id}/finalize` | POST | Unlock FHIR export |
| FHIR result | `/fhir?packet_id=` | GET | Honest export metadata + download |
| Bundle JSON | `/fhir/bundle?packet_id=` | GET | Raw Bundle (FINALIZED only) |
| Reviewer queue | `/review` | GET | NEEDS_REVIEW worklist (oldest first) |
| Reviewer detail | `/review/{id}` | GET | Data, findings, evidence meta, provenance |
| Accept | `/review/{id}/accept` | POST | → CONFIRMED (not FHIR) |
| Reject | `/review/{id}/reject` | POST | → REJECTED (reason_code required) |
| Edit | `/review/{id}/edit` | POST | Fields + FlagEngine; stay NEEDS_REVIEW |

Mutations are **POST only**. Confirm ≠ finalize. Accept ≠ finalize. No GET mutations.

## 3. Submission UX

- Site select from `app.domain.sites` (single catalog; no duplicated city lists).
- Human-readable labels (foam, colour, smell, vegetation, channel) — **no FHIR jargon**.
- Unsupported / excluded indicators (BMWP, pathogen, …) rejected in the form adapter.
- Photo optional; noted in provenance for demo (full media pipeline later).
- Core path: SQLite + `DeterministicFlagEngine` + `NullAiAssist` + `NullFhirValidator`.

## 4. Flag presentation

| Group | Severities | UX effect |
|---|---|---|
| **Needs correction** | `hard_reject`, `soft_block_finalize` | Confirm disabled until empty (soft cannot be fixed after confirm) |
| **Warnings** | `warn` | Advisory only |

No trust score, confidence %, or composite fitness metric.

Guidance is plain language (what to fix), not rule-engine jargon alone.

Reviewer detail shows full findings: human message + `rule_id` / `code` / `severity` / field / ruleset. Flags are not dismissable.

## 5. Authority chain (always visible)

1. Pre-confirm evaluation (rules engine)  
2. AI optional — never authority  
3. Human confirm freezes snapshot  
4. Explicit finalize unlocks export  
5. FHIR from finalized snapshot only  

Non-claim copy on every citizen/FHIR surface (SEC-008).

## 6. Correction / revalidation

- Citizen edits allowed only while `FLAGGED` (domain matrix).
- Reviewer edits allowed while `NEEDS_REVIEW`.
- Same `packet_id`; `replace_fields` clears stale flags; engine re-runs immediately.
- Stale flags are never shown as authoritative after a successful correct/edit POST.

## 7. Confirmation UX

- Separate button: “Confirm observation (human authority)”.
- Copy states this does **not** export FHIR.
- Blocked when Needs correction is non-empty or standing `hard_reject`.

## 8. Finalization UX

- Separate button after `CONFIRMED`.
- Optional cited One Health sentence (non-diagnostic template default).
- On failure, show domain / StructuralGuard refusal reasons honestly.

## 9. FHIR export UX

Honest metadata only:

- Mapper version, ruleset version, IG version (reference)
- Bundle hash, resource count, bundle type
- Profiles claimed as **structural** (not “validator green”)
- Validation status: `not_run` under `NullFhirValidator`
- Supported export scope text (foam / macrophytes / riparian / hydromorphology; colour/smell annotation)

Never claim OAH IG validated unless a real validator ran and passed.

## 10. Reviewer desk UX (Phase 7)

- Worklist columns: packet id, site, time, flag severity/count, state, concise review reason.  
- **Not** a BI dashboard (no charts, KPIs, trust scores).  
- Accept copy: does not export FHIR.  
- Reject: required structured reason codes + optional explanation.  
- Concurrency: hidden `revision` field; stale → clear conflict message.  
- Auth disclosed: demo reviewer Actor; not a security boundary.

## 11. Errors

Mapped in `app/web/errors.py` to short citizen/reviewer messages + HTTP status.  
Form field errors redisplay on the form.  
Persistence failures do not leak SQL.

## 12. Accessibility baseline

- Skip link, language, labels tied to controls, fieldsets/legends
- `role="alert"` for errors; `role="status"` for gate messages
- Visible focus rings; semantic headings; worklist `<table>` with caption/`scope`
- Contrast-oriented civic palette (not decorative AI-dashboard chrome)

## 13. Responsive

- Single-column max ~40rem; stacked actions on narrow viewports
- Touch-friendly controls; full-width primary buttons on small screens

## 14. Security / observability (hackathon)

- Server-side validation + Jinja auto-escape
- Opaque packet ids; **no multi-user auth yet** (disclosed in footer + HITL-POLICY)
- Structured logs: event name + packet_id / counts / versions — **no** full payloads, media bytes, or secrets

## 15. Demo path

Fixture: `tests/fixtures/demo_coimbra_sensory.json` — same domain path as production submit (no hardcoded packet_id branches).

Manual 90s: Coimbra + foam/colour/smell → flags clear → confirm → finalize → `/fhir`.  
Optional AI: blank sensory field + `AI_PROVIDER=fake` → advisory panel → Use suggestion / Keep my value.  
Reviewer: submit → Send to reviewer → accept/edit/reject on `/review` (AI panel visible if present).

---

*Phase 6–8 UX contract. Phase 9 = security / EXIF.*
