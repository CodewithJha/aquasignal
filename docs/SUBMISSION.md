# ConfirmGate submission checklist

> **Product:** ConfirmGate + AquaSignal (see `docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md`, `docs/AQUASIGNAL-ARCHITECTURE-SPIKE.md`, `docs/DEMO.md`). StreamWitness factsheet-checklist thesis is superseded — keep `docs/WIN-PLAN.md` as historical only.

Devpost deadline **4 Oct 2026 9:00 PM PDT** (5 Oct 2026 09:30 IST). Submit early; do not wait for deadline day.

## Before you can submit

- [ ] Registered on https://oneaquahealth-ieee-hackathon.devpost.com/
- [ ] Draft submission started (see real form)
- [ ] Joined Slack: https://join.slack.com/t/oneaquahealth-f8b4365/shared_invite/zt-4a9yfki2p-hGklHIbz4FAvy2dz7mlDYQ
- [ ] Factsheets + protocols PDFs downloaded

## Product

- [ ] Track named: **Track 3 — AI-Supported Assessment**
- [ ] Deployed public URL (not localhost, not a notebook, not Streamlit-only)
- [ ] `/upload` — city + protocol-lite fields + optional photo filename + notes
- [ ] Deterministic quality flags (no trust score); AI optional / Null-first
- [ ] Human confirm/edit required; FHIR only after finalize (`status=final` only)
- [ ] `/fhir` shows Location + Observation Bundle (OAH subset; HL7 validator vs CI-build IG: 0 errors, 5 narrative warnings — see `docs/FHIR-SPEC.md` §9.1)
- [ ] `/investigate` AquaSignal brief: SYSTEM ANALYSIS / AI ADVISORY / HUMAN DECISION
- [ ] Synthetic fixtures labelled **SYNTHETIC FIXTURE**; no pollution/pathogen claims
- [ ] Append-only provenance / audit trail
- [ ] Five cities seeded: Coimbra, Benevento, Ghent, Oslo, Toulouse
- [ ] Optional read-only links to CS app, Resilience Map, GEOSSIP — apps not rebuilt
- [ ] GitHub **public** with commits on/after **14 Sep 2026** (do not backdate)

## Devpost packet

- [ ] Problem / solution / users
- [ ] Ecosystem + **human health** impact (One Health)
- [ ] Video **3–5 minutes**
- [ ] Public GitHub URL
- [ ] Working prototype URL
- [ ] AI tools disclosed

## Video script beat sheet

1. 0:00–0:30 — “Track 3. Citizen stream reports are inconsistent, so One Health decisions can’t use them.” Screen: upload → flags → confirm → finalize → FHIR. “Human remains the authority.”
2. ConfirmGate citizen + finalize-only FHIR
3. AquaSignal investigation brief (conflict / temporal / insufficient) — SYNTHETIC FIXTURE labelled
4. Reproducibility hashes + Null AI advisory (optional)
5. Coimbra close: evidence patterns, not pollution diagnosis
6. Stop by ~4:30. Never go past 5:00.

## README must include (this order)

Track | problem | **live URL** | architecture | HITL policy | FHIR resources | factsheets used | commits in period | AI disclosure | 3-command run | license

## After submit

- [ ] Demo stays up through judging (**5 Oct 9:00 AM PDT – 15 Oct 2026 5:00 PM PDT**; winners 24 Oct at IEEE iGET)
- [ ] Do not take the site down to “clean up”
