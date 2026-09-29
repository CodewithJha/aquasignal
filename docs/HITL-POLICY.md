# ConfirmGate — HITL Policy (Phase 7)

Status: ACTIVE (Phase 7)  
Date: 21 Sep 2026  
Authority: `docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md`, `docs/REQUIREMENTS.md` HITL-001–005

## 1. Authority

**Human confirmation is authority.** AI suggestions are never authoritative. Deterministic FlagEngine raises structured quality flags; flags are not a 0–100 trust score and are not authority.

| Actor | May |
|---|---|
| Citizen (packet author) | Submit, correct while `FLAGGED`, confirm (`AWAITING_CONFIRM`→`CONFIRMED`), request review, finalize after confirm |
| Reviewer (demo Actor) | Escalate from `FLAGGED`, edit while `NEEDS_REVIEW`, accept → `CONFIRMED`, reject → `REJECTED` |
| System | Apply FlagEngine, queue review, support finalize |
| AI provider | Suggestions only — cannot confirm, accept, reject, finalize, or write authoritative fields. Human must explicitly Use suggestion / Keep my value. See `docs/AI-POLICY.md`. |

## 2. Confirm ≠ finalize ≠ FHIR

1. **Accept / confirm** freezes a confirmation snapshot and moves the packet to `CONFIRMED`.  
2. **Finalize** is a separate transition (`CONFIRMED` → `FINALIZED`).  
3. **FHIR export** is allowed only at `FINALIZED` (`status=final` only).  
4. Reviewer **accept does not export FHIR** and does not auto-finalize.

## 3. Reviewer actions (exact states)

No new workflow states. No `UNDER_REVIEW` / `APPROVED`.

| Action | Transition | Notes |
|---|---|---|
| Escalate / request review | `FLAGGED` → `NEEDS_REVIEW` | Explicit; soft_block alone does **not** auto-escalate |
| Accept | `NEEDS_REVIEW` → `CONFIRMED` | Blocked by standing non-overridden `hard_reject` |
| Reject | `NEEDS_REVIEW` → `REJECTED` | Structured `reason_code` required |
| Edit + revalidate | stays `NEEDS_REVIEW` | Domain mutators → DeterministicFlagEngine; flags replaced, not dismissed |
| Finalize | `CONFIRMED` → `FINALIZED` | Existing citizen/system path; not part of accept |

## 4. Rejection reason codes

ConfirmGate ops codes (not OAH FHIR codes):

- `unsupported_observation`
- `insufficient_evidence`
- `invalid_site`
- `prohibited_claim`
- `inconsistent_submission`
- `other` (+ optional free-text explanation)

Empty `reason_code` is refused. Unknown codes are refused.

## 5. Hard vs soft flags

| Severity | Confirm / accept | Finalize / FHIR |
|---|---|---|
| `hard_reject` (standing) | Blocks | Blocks |
| `soft_block_finalize` (standing) | Does **not** block | Blocks |
| `warn` | Advisory | Advisory |

`soft_block_finalize` does **not** mean the packet is invalid or `REJECTED`. Phase 6 citizen soft-block UX remains: soft items appear under Needs correction for citizen confirm hygiene; domain still allows confirm without soft clearance once hard flags are clear — citizen UX may still gate confirm on soft for demo clarity. Reviewer accept uses domain rules (hard only).

## 6. Revalidation on edit

Reviewer field edits while `NEEDS_REVIEW`:

1. Clear flag snapshot (domain).  
2. Run injected `DeterministicFlagEngine`.  
3. Attach new flags; remain in `NEEDS_REVIEW`.  
4. Persist packet + provenance in one transaction.

No flag delete/dismiss UI. No silent mutation of a confirmation snapshot (packet is unconfirmed until accept).

## 7. Provenance

Append-only durable log answers HITL audit questions. Reviewer decisions emit at least:

- `review.queued` (escalate)
- `fields.replaced` / `fields.set` (edit)
- `flags.raised` (revalidate)
- `review.accepted` (accept)
- `review.rejected` (reject from desk)

Provenance cannot be removed via application APIs.

## 8. Concurrency

Optimistic `revision` on `PacketRecord`. Stale reviewer POSTs with mismatched revision raise a clear conflict — no silent overwrite.

## 9. Auth limitation (explicit)

**Authentication and authorization are not implemented.** The composition root injects a demo reviewer `Actor` (`demo-reviewer`). `/review` is not an access-control boundary. Do not put personal data on a public demo URL and treat links as opaque identifiers only. Real auth is Phase 9+.

## 10. Safety refusals

The system must refuse to:

- Invent OAH TemporaryOahSystem codes outside the verified mapper
- Bypass StructuralGuard
- Export FHIR for `CONFIRMED` (or any non-`FINALIZED`) packets
- Finalize `REJECTED` packets
- Remove or rewrite provenance history
- Overwrite on stale revision

---

*Phase 7–8 HITL contract. Phase 8 AI never auto-accepts. Phase 9 = security / auth.*
