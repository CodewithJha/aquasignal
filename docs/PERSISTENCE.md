# ConfirmGate — Persistence (Phase 4)

Status: ACTIVE (Phase 4)  
Date: 21 Sep 2026  
Authority: `docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md`, PROV-001–002, FR-004

## Architecture

```text
domain  (stdlib only; rehydrate; ProvenanceIntent)
   ↑
application  (ports + ObservationService + PacketDocument DTO)
   ↑
persistence/sqlite  (migrations, repos, UnitOfWork)
   ↑
web  (lazy ObservationService adapter — no UX redesign)
```

Dependency rule: domain never imports application/persistence/web/fhir/ai/sqlite3.  
Flags never import persistence; `SqliteDuplicateLookup` is injected at composition root.

## Technology and rationale

**SQLite** file DB + small ordered SQL migrations (not Alembic).

- Zero ops for hackathon deploy; stdlib `sqlite3`; easy temp DBs in tests.
- Ports (`ObservationPacketRepository`, `ProvenanceRepository`, `UnitOfWork`) allow a future Postgres adapter without rewriting domain/application.
- Explicit JSON document column (not ORM-as-domain, not pickle).

## Repository contracts

| Port | Methods | Notes |
|---|---|---|
| `ObservationPacketRepository` | `get`, `exists`, `save(expected_revision=)`, `list_ids_for_site`, `list_for_review` | Intent API — no `execute_sql`. `list_for_review`: NEEDS_REVIEW filter; oldest `created_at` first |
| `ProvenanceRepository` | `append`, `append_many`, `list_for_packet` | **No** update/delete |
| `UnitOfWork` | `packets`, `provenance`, `commit`/`rollback` | Shared connection/tx |

`PacketRecord` = reconstructed `ObservationPacket` + `revision` (+ timestamps).

## Serialization model

1. Domain aggregate → `packet_to_document()` → versioned DTO (`document_version=1`)  
2. DTO → deterministic JSON (`sort_keys=True`, compact separators)  
3. JSON text → `observation_packets.document_json`  
4. Reload: JSON → DTO → `ObservationPacket.rehydrate()` (no provenance emission)

Reconstructs: identity, site, fields+source, flags snapshot, workflow, confirmation snapshot+hash, actors/ids, notes, suggestions, rule_engine_version, export metadata.  
**Not stored:** secrets, raw image bytes, API keys.

## Database schema (v1)

- `schema_migrations(version, applied_at, name)`
- `observation_packets(packet_id PK, site_ref_id, city, workflow_state, revision, document_json, flags_rules_version, created_at, updated_at)`
- `provenance_events(seq PK AUTOINCREMENT, event_id UNIQUE, packet_id FK, at, actor_*, action, before/after JSON, model_id, prompt_version, rule_engine_version)`

DB constraints enforce storage integrity only. Business rules stay in domain.

## Migration strategy

Ordered files under `app/persistence/migrations/` (`001_initial.sql`, …).  
`apply_migrations()` applies pending versions transactionally and records them. Reviewable SQL; no Alembic required for hackathon.

**Startup:** migrations run **automatically** when the app opens the DB (`prepare_database` / composition root). There is no separate migrate CLI. Empty `DATABASE_URL` file → first start creates schema.

## Transaction model

`ObservationService` persists **packet save + drained ProvenanceIntent append** in one `UnitOfWork`.  
If provenance append fails → rollback → packet insert/update is not durable.

## Concurrency model

Optimistic concurrency via integer `revision`:

- Insert: `expected_revision=0` → stored revision `1`
- Update: `WHERE packet_id=? AND revision=?` then `revision+1`
- Stale → `ConcurrencyConflict` (clear application error; no raw sqlite)

## Provenance model

Append-only durable log from Phase 2 `ProvenanceIntent` (actor, action, when, packet, before/after, model/prompt, rule_engine_version).  
Monotonic `seq` orders events per store. Answers spike Part 8 HITL questions via `answer_hitl_audit_questions`. Phase 5 records `bundle_hash` + `mapper_version` on `fhir.export_digest` (and optionally on `fhir.exported`).  
Optional hash-chain **skipped** (complexity > value; not blockchain).

## Flag snapshot persistence

Latest flags are stored inside the packet document with `flags_rules_version` (= `rule_engine_version` from `apply_flags`).  
Persisted flags are a **snapshot**, not live engine truth. Application must re-run FlagEngine when `FLAG_RULES_VERSION` advances before treating flags as current. Persistence never auto-evaluates flags.

## Recovery / restart

Close connection → open new connection to same file → `get` + `list_provenance` reconstruct full aggregate and ordered audit. Tests simulate this with temp DBs.

## Security

- Parameterized SQL only (`?` placeholders).
- Opaque UUID-hex `packet_id` (FR-004).
- No secrets in provenance payloads by design; notes are plain text only.
- `DATABASE_URL` / default path; `.env` local only.
- Default path: `<repo>/data/confirmgate.sqlite3` (gitignored).

## Postgres path (future)

Implement the same ports with `psycopg` (or similar), keep PacketDocument JSON (JSONB), keep revision OCC, keep append-only provenance table. No domain changes required.

## Config

```bash
# .env
DATABASE_URL=sqlite:///data/confirmgate.sqlite3
```

Empty / unset → safe default under project `data/`.

---

## AquaSignal Phase A2/A4 notes

Migration `002_aquasignal.sql` adds evidence / snapshot / run / signal / relation / case tables alongside ConfirmGate. Shared `SqliteUnitOfWork` exposes both packet and AquaSignal repos.

**FK save order (A4 persist path):** `evidence_items` → `evidence_snapshots` (+ members) → `analysis_runs` (STARTED) → `environmental_signals` (+ signal_evidence) → `analysis_runs` (SUCCEEDED + signal ids) → `evidence_relations`. Optional `investigation_cases` after SUCCEEDED run via `InvestigationService` (signals must exist for `case_signals` FK).

**A4 application:** `AnalysisService` / `InvestigationService` use ports only — no SQL in application. Analysis history is append-only (new `run_id` each analyze; repo refuses overwrite of SUCCEEDED/FAILED). Provenance analysis events reuse `provenance_events` keyed by ConfirmGate `packet_id`.

**A5 retrieval:** `AnalysisRunRepository.list_for_site` joins snapshot members → evidence_items; `EvidenceSnapshotRepository.find_for_hash` resolves the snapshot for a run. `InvestigationBriefService` reads only — never re-runs detectors.
