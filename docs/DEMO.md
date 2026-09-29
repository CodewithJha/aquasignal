# Demo path: ConfirmGate + AquaSignal

Status: current, after the P0–P2 integration, hardening, and deployment passes. Runs with no AI key.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export AI_PROVIDER=null                      # default; shown for clarity
# optional: export DATABASE_URL=sqlite:///data/demo.sqlite3   (fresh demo DB)
python scripts/seed_aquasignal_demo.py       # optional synthetic Coimbra runs
uvicorn app.main:app --port 8000
```

With Docker: `docker run --rm -p 8000:8000 -v confirmgate-data:/data confirmgate`, then optionally `docker exec <container> python scripts/seed_aquasignal_demo.py`.

The schema migrates automatically on start. `GET /healthz` should return `{"status":"ok","database":"ok"}`.

## Live flow (about 3–4 minutes)

| # | Where | Action | What to point out |
|---|---|---|---|
| 1 | `/upload` | Pick **Coimbra**, fill foam, colour, and smell, optionally attach a photo | Only the photo's file name is recorded. "Image content is not analyzed by this system." |
| 2 | `/observation/{id}` | Review the deterministic flags, correct a field if needed | Structured flags with severity and rule id. No trust score. |
| 3 | same | **Confirm**, then **Finalize** (with the cited One Health sentence) | The human is the authority. Nothing becomes authoritative before this. |
| 4 | `/fhir` | Try it before finalize (refused), then after | Bundle with `Location` and `Observation` resources, `status=final` only. OAH subset; HL7 validator vs CI-build IG: 0 errors (see `docs/FHIR-SPEC.md` §9.1). |
| 5 | `/investigate/sites/coimbra` | Press **Analyze finalized observations** | Explicit, human-triggered. Freezes a snapshot of FINALIZED packets and runs the 2 detectors. |
| 6 | `/investigate/analyses/{run_id}` | Read the brief: Investigation summary → What we found → Why? (top 3 disagreeing pairs, the rest under *Show all*) → Evidence → Human decision → Technical details | A signal is an evidence pattern worth investigating, not a finding about the water. Two same-visit submissions with different foam values show **1 observation pair disagrees about foam**; the temporal baseline shows **insufficient evidence**. That is the honest result. |
| 7 | same | **Open investigation case** | HUMAN DECISION layer |
| 8 | same | Pick a decision (e.g. *Request more evidence*), write a rationale, **Record human decision** | Attributed to the demo reviewer, version-checked, append-only |
| 9 | same | AI advisory line | With `AI_PROVIDER=null` it shows "AI advisory: disabled. Deterministic analysis is complete without it." A timeout or provider error shows "AI advisory unavailable … Deterministic analysis remains available." |
| 10 | Technical details (collapsed) | Show snapshot hash, parameters hash, detector set and detector versions | Same evidence gives the same hashes. The snapshot hash also covers the canonicalization version (`vocab-canon@1`). |

## Seeded synthetic runs (Coimbra)

`scripts/seed_aquasignal_demo.py` appends three SUCCEEDED runs built from 29 hand-made rows and never overwrites earlier runs. The UI labels every fixture row **SYNTHETIC FIXTURE**.

| Run | Fixtures | Rows | Current result |
|---|---|---|---|
| 1 (primary brief) | `A_temporal_shift` + `C_contradiction` | 14 | `temporal_shift` + `contradiction`: 3 observation pairs compared, **2 disagree about foam** (recorded 1–2 h apart on 10 Sep), 1 agrees; opens an example case |
| 2 | `E_insufficient` | 3 | temporal `insufficient_evidence`; no contradiction (no two rows within the 24 h comparison window) |
| 3 | `B_stable_control` | 12 | **no signals.** `absent`/`none` are canonicalized before detection, so they no longer conflict. This is not a claim that the water is safe. |

`D_duplicate_support` (3 rows) exists for tests and manual loads only and is not seeded. It yields one duplicate pair (identical values, same timestamp); its third row is four days later and gets no relation.

Contradictions compare only observations recorded within 24 h of each other (same visit), and identical observations within 10 minutes count as one duplicate pair. `C_contradiction`'s second row was moved from 12 Sep to 10 Sep 11:00 (still synthetic) so the demo keeps an honest same-visit disagreement. Details: `docs/SIGNAL-ENGINE.md`.

Seeded sites use **city-centroid** coordinates, which are a demo position rather than a sampling station.

## Narrative lines

- "Citizen reports become usable only after a human confirms them, and FHIR exists only after finalize."
- "AquaSignal doesn't detect pollution. It detects when the evidence deserves investigation, reproducibly, and a human decides."
- "AI is optional. Everything you just saw ran with AI switched off."

## Copy discipline

Do not say: pollution detected, contamination, pathogen, disease, outbreak, health risk, water is safe/unsafe, trust score, confidence %, Good/Bad/Healthy stream, "AI analyzes the photo".

## JSON API (read-only)

- `GET /api/sites/coimbra/analyses`
- `GET /api/analyses/{run_id}` (plus `/signals`, `/evidence`, `/reproducibility`)
