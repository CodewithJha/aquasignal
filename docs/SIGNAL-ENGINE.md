# AquaSignal Signal Engine (Phase A3)

Status: ACTIVE (A3)  
Authority: `docs/AQUASIGNAL-ARCHITECTURE-SPIKE.md`  
Date: 22 Sep 2026  

## Purpose

Pure deterministic analysis:

```text
EvidenceObservation[] + AnalysisContext → SignalEngine → SignalResult[]
```

No persistence, UI, AI, FHIR, or ConfirmGate FINALIZED gate (A4 owns eligibility).

## Contract

- **`SignalDetector`**: `detector_id`, `detector_version`, `analyze(evidence, context) → SignalResult[]`
- **`AnalysisContext`**: `site`, `time_window`, `params` — no repo/HTTP/AI
- **`SignalResult`**: status ∈ {insufficient_evidence, no_meaningful_shift, signal}; optional `signal_type`; metrics; explanation; relations; **no random IDs**
- **Registry**: fixed order `temporal_baseline_shift:v1` then `cross_observation_contradiction:v2` (detector set `aquasignal-detectors-a3-v2`)

## Detectors

| Id | Version | Notes |
|---|---|---|
| `temporal_baseline_shift` | `v1` | Ordinal median + MAD; zero MAD → absolute threshold 1.0 ordinal step |
| `cross_observation_contradiction` | `v2` | Same-visit protocol compare inside a 24 h comparison window; supports / conflicts / duplicates; canonical pair order (see below) |

## Contradiction semantics (v2)

`ContradictionParams` (all fields enter `parameters_hash`):

| Param | Default | Meaning |
|---|---|---|
| `comparison_window` | 24 h | Only observation pairs with \|Δt\| ≤ window are compared. Pairs further apart get **no relation** (neither support nor conflict). Independent of the overall analysis window. |
| `duplicate_max_delta` | 10 min | Must be ≤ `comparison_window`. |
| `field_codes` | foam, macrophytes, riparian_vegetation, hydromorphology, colour, smell | Compared fields (controlled vocabulary only). |
| `minimum_comparable_observations` | 2 | Below this → `insufficient_evidence` (unchanged from v1). |

Per observation pair inside the window, over the fields both observations carry:

- **Duplicate pair**: \|Δt\| ≤ `duplicate_max_delta` **and** every shared field equal → every shared field gets a `duplicates` relation and never also `supports`.
- Otherwise each shared field: equal → `supports`, different → `conflicts`. A near-simultaneous pair that differs on any field is not a duplicate.

Field-level relations are persisted as before. The investigation brief derives observation-pair counts from them (pairs compared, pairs that disagree = ≥ 1 conflicting field, pairs that agree, duplicate pairs); nothing new is persisted. New metrics on the detector result: `pairs_compared`, `pairs_outside_comparison_window`, `conflicting_pair_count`, `agreeing_pair_count`, `duplicate_pair_count`, `comparison_window_seconds`.

If there are enough comparable observations but no pair falls inside the window, the result is `no_meaningful_shift` with a summary that says no same-visit comparison was possible (the insufficiency rule is unchanged).

Why these values: ConfirmGate records the observation time at submit, and a single stream visit fits within a day, so 24 h scopes "same visit". Observations days or months apart describe different conditions and are the temporal detector's job. The ConfirmGate duplicate flag rule has no time notion (it matches on site only), so there was nothing to align with. 10 minutes covers a double tap or immediate re-upload while staying far below the visit window.

v1 (runs with detector set `aquasignal-detectors-a3-v1`) compared every pair inside the whole analysis window (up to 120 days) and treated only Δt = 0 as a duplicate, so separate visits months apart were reported as contradictions. Persisted v1 runs are immutable and still render; the brief shows their real time gaps.

## Ordinals

Explicit maps only: foam, macrophytes, hydromorphology, riparian_vegetation (`app/signals/ordinals.py`). Colour/smell are categorical for contradiction only.

## Dependency rule

`app/signals` may import `app.domain` and `app.flags.schema`. Must not import `app.persistence`, `app.web`, `app.ai`, `app.fhir`, `app.application`, or `sqlite3`.

## Phase A4 consumer

`AnalysisService` builds `EvidenceObservation[]` from FINALIZED packets + fixtures, calls `SignalEngine.analyze`, maps `SignalResult` → durable `EnvironmentalSignal` / `EvidenceRelation`, and stores `detector_set_version` + `parameters_hash` on `AnalysisRun`. Detectors remain pure; they never see the FINALIZED gate.
