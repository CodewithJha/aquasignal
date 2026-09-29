# ConfirmGate — FlagEngine Contract (Phase 3)

Status: DRAFT  
Version: 0.1.0 (`FLAG_RULES_VERSION`)  
Date: 21 Sep 2026  
Authority: `docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md`, `docs/REQUIREMENTS.md`

## Purpose

`DeterministicFlagEngine.evaluate(packet) → list[QualityFlag]` answers:

> What is wrong, incomplete, risky, inconsistent, or worth reviewing?

It does **not** produce a trust/confidence/composite score.

Evaluation is pure: no workflow mutation, no FHIR, no AI, no I/O.

## Architecture

```text
DeterministicFlagEngine
 ├── CompletenessRule
 ├── VocabularyRule
 ├── NonClaimRule
 ├── GeoRule
 ├── MediaRule          ← MediaContextProvider (null = unbound no-op)
 ├── MediaHeuristicRule ← safe no-op until deterministic signals exist
 ├── ExifRule           ← only when media context bound + EXIF present
 ├── DuplicateRule      ← DuplicateLookup (null = no matches)
 ├── FhirReadinessRule  ← domain prerequisites only (no FHIR libs)
 └── AiAssistRule      ← Phase 3 stub (always empty)
```

## Severity (enforced by domain, reported by engine)

| Severity | Engine meaning | Domain effect (Phase 2) |
|---|---|---|
| `hard_reject` | Invalid / prohibited | Blocks confirm |
| `soft_block_finalize` | Not export-ready | Blocks finalize; does **not** block confirm |
| `warn` | Advisory | Blocks nothing |

## Schema notes **[VERIFY]**

- Field codes = internal citizen-safe allowlist (`app/domain` / `app/flags/schema.py`), **not** TemporaryOahSystem URIs.
- `REQUIRED_FOR_FINALIZE` = provisional sensory triad `{foam, colour, smell}`.
- Vocabularies are domain-local enums pending Annex I / IG confirmation.

## Ports (not implemented systems)

| Port | Phase 3 default | Future |
|---|---|---|
| `MediaContextProvider` | `bound=False` → media/EXIF quiet | Phase 9 media/EXIF |
| `DuplicateLookup` | empty matches | **Phase 4:** `SqliteDuplicateLookup` (same `site_ref_id`) |

## Flag snapshots vs live engine (Phase 4)

Persisted packets store the latest flag list plus `flags_rules_version` / `rule_engine_version` from `apply_flags`.  
That snapshot must not silently override a newer `FLAG_RULES_VERSION` as truth — application re-eval is required after engine upgrades. Persistence never auto-runs the engine.

## Determinism

Same packet + `FLAG_RULES_VERSION` → same flags including `flag_id` (content hash).  
Flags sorted by severity → `rule_id` → `code` → `message` → `flag_id`.
