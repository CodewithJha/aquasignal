# ConfirmGate — instructions for the next agent

You are working in this repository. It is **only** for the OneAquaHealth IEEE Global Hackathon.

## Authority (read before coding)

1. **`docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md`** — product thesis, domain, state machine, FHIR, kill criteria  
2. **`docs/PHASE1-AUDIT.md`** — what Phase 1 did / did not do  
3. Existing code only where it does not contradict the above  

`docs/WIN-PLAN.md` and older StreamWitness copy are **superseded** by the ConfirmGate spike. Do not rebuild the factsheet checklist thesis.

## Who you are helping

No teammates. Timezone IST (UTC+5:30).

Strong: AI, LLMs, AI agents, backend, ML, data science. Also CV, speech, fullstack, APIs, DevTools, OSS.

Do **not** build Web3, blockchain, cyber/offensive-security, composite trust scores, multi-agent swarms, or photo→BMWP/pathogen/Diptera prediction.

## Mission

Ship **ConfirmGate**: Track 3 observation integrity lifecycle.

Core flow:

1. Citizen submits protocol-lite fields (Annex I subset) + photo evidence for one of five OAH cities.  
2. Deterministic **FlagEngine** raises structured quality flags (no 0–100 trust score).  
3. Optional **AiAssistPort** suggestions (NullAiAssist must work with no API keys). AI is never authority.  
4. Human **must confirm or edit** before anything is authoritative.  
5. Only after finalize: export IG-shaped FHIR `Location` + `Observation` (`status=final` only) + Provenance + one cited One Health sentence.  
6. Append-only provenance answers the seven HITL audit questions in the spike.

Product is a **deployed web app** (`/upload`, confirm surface, `/fhir`, secondary `/review` desk later). Not Streamlit-only. Not a notebook.

**Never** emit `Observation.status = preliminary`. Prefer exporter refusal over invalid Bundles. Do not claim full OAH IG validator green until StructuralGuard + real TemporaryOahSystem mapping exist.

The five OAH cities: **Coimbra, Benevento, Ghent, Oslo, Toulouse**. Seed them. Do not invent extra official cities.

## Forbidden reintroductions

- StreamWitness “factsheet checklist” AI draft of habitat / macroinvertebrates / Diptera / water quality / well-being as the product core  
- `draft_from_checklist` as AI architecture  
- FHIR preliminary path for unconfirmed sessions  
- Composite trust score  
- AI required to complete the demo  
- Lab indicators (diatoms, BMWP, ARG, pathogens, etc.) as citizen AI-draftable fields  

## Deadlines (hard)

- Submit before the Devpost deadline. Do not wait for deadline day.  
- Hard clock (Devpost): **4 Oct 2026, 9:00 PM PDT = 5 Oct 2026, 09:30 IST**.  
- Judging: **5 Oct 2026 9:00 AM PDT – 15 Oct 2026 5:00 PM PDT**. Keep the demo URL alive through judging.  
- Winners: **24 Oct 2026** at IEEE iGET.  

Original work: **git commits on/after 14 Sep 2026**. Do not backdate.

## Judging (official weights)

| Criterion | Weight |
|---|---|
| Impact & alignment with OneAquaHealth | **30%** |
| Innovation | 20% |
| Technical implementation | 20% |
| Usability & UX | 15% |
| Feasibility & scale | 15% |

## Stack

Modular FastAPI monolith: `app/domain`, `app/flags`, `app/ai`, `app/fhir`, `app/provenance`, `app/web`. Thin `app/main.py`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest
```

## Official links (do not drop)

- Devpost: https://oneaquahealth-ieee-hackathon.devpost.com/
- Official page: https://www.oneaquahealth.eu/oneaquahealth-ieee-global-hackathon/
- Email: oneaquahealth@ieee.org
- Slack: https://join.slack.com/t/oneaquahealth-f8b4365/shared_invite/zt-4a9yfki2p-hGklHIbz4FAvy2dz7mlDYQ
- Factsheets PDF: https://www.oneaquahealth.eu/app/uploads/2026/09/FactSheets_Combined_zenodo_f_citation_F_16092026.pdf
- Field protocols PDF: https://www.oneaquahealth.eu/app/uploads/2026/09/Field-Sampling-protocols-OAH_citation_Final_16092026.pdf
- FHIR IG: https://github.com/hl7-eu/oah
- CS app: https://apps.oneaquahealth.eu/login
- Resilience Map: https://apps.oneaquahealth.eu/resmap/
- GEOSSIP: https://apps.oneaquahealth.eu/eo
- Recordings: https://www.oneaquahealth.eu/project-events/ (Session 4 is FHIR)

## Working rules

- Prefer a 90-second honest demo over extra models.  
- Every AI output is suggestion-only until human confirm.  
- No secrets in git. Use `.env` locally; never commit keys.  
- Phase sequencing: do not start the next phase until the user approves. Next after Phase 1: real ObservationPacket + workflow state machine with illegal-transition tests.
