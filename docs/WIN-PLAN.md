# StreamWitness win plan — OneAquaHealth IEEE Global Hackathon

> **INTERNAL / SUPERSEDED — historical research, not a description of the shipped product.** Current docs: [`docs/README.md`](README.md).

> **SUPERSEDED for product thesis.** Build **ConfirmGate** per `docs/CONFIRMGATE-ARCHITECTURE-SPIKE.md` and `docs/PHASE1-AUDIT.md`. Do not follow the StreamWitness factsheet-checklist / vision-draft path below as the product core.

IST. Track 3 only.

## What they actually want

Urban freshwater + **One Health** (human + animal + environment). Not a generic water-ML demo.

Tagline to align with: *From streams to systems: turning citizen science into actionable One Health intelligence.*

AI may **draft and validate**. It must **not replace human judgment**. FHIR is the data contract. Stay in **Track 3 (AI-Supported Assessment)** unless the product becomes FHIR-first — then Track 7 is the alternative, not an extra submission.

## Deadlines

> Dates below reflect the original schedule. Current Devpost deadline: **4 Oct 2026, 9:00 PM PDT (5 Oct 2026, 09:30 IST)**; judging 5–15 Oct; winners 24 Oct.

| Event | When |
|---|---|
| Submit | **29 Sep 2026** (do not use deadline day) |
| Hard clock | 30 Sep 2026 9:00 PM PDT = **1 Oct 2026 09:30 IST** |
| Judging | 1–15 Oct 2026 |
| Winners | 24 Oct 2026, IEEE iGET |
| Original work | commits **on/after 14 Sep 2026** |

## Calendar

- **21 Sep:** setup, Devpost draft, Slack, download PDFs, placeholder `/upload` `/review` `/fhir`
- **22–24 Sep:** MVP deployed — photo → quality reject → drafted checklist → human confirm → FHIR JSON + download
- **25–28 Sep:** reviewer view, audit log, 5-city picker, diagram, 3–5 min video, README, AI disclosure
- **29 Sep:** submit. Public GitHub. Live URL.
- **30 Sep:** buffer only

## Judging weights

Ten domain judges (ecology, FHIR, their Hub). ~949 registrants. They watch the **video** and skim Devpost first. Repo is a finalist check. No live pitch.

| Criterion | Weight |
|---|---|
| Impact & alignment with OneAquaHealth | **30%** |
| Innovation | 20% |
| Technical implementation | 20% |
| Usability & UX | 15% |
| Feasibility & scale | 15% |

## Product: StreamWitness

Citizen observation in **OAH’s own language** (factsheet indicators):

- habitat
- macroinvertebrates
- Diptera / mosquitoes
- water quality
- well-being

Then:

1. Model drafts what it sees (labeled DRAFT)
2. Citizen **must confirm or edit**
3. System writes FHIR `Location` + `Observation`
4. Confirm/reject + audit trail
5. One Health sentence for a named user (citizen or city officer)
6. Demoable in **90 seconds**

Seed cities: **Coimbra, Benevento, Ghent, Oslo, Toulouse**.

Optional read-only links (do not rebuild):

- CS app: https://apps.oneaquahealth.eu/login
- Resilience Map: https://apps.oneaquahealth.eu/resmap/
- GEOSSIP: https://apps.oneaquahealth.eu/eo

## Video (3–5 min, not shorter, not longer)

First 30 seconds:

> Track 3. Citizen stream reports are inconsistent, so One Health decisions can’t use them.

Then screen recording: photo → AI draft → human confirm → FHIR JSON. “Human remains the authority.” Then one citizen flow, one reviewer flow, one FHIR payload, one Coimbra/Ghent “what next.” Stop by 4:30.

## What currently loses

Streamlit maps, notebooks, fake-sensor Isolation Forests. A dashboard without One Health, their CS app, or the five cities loses to a plainer HITL tool that writes a real FHIR Observation.

## Do not build

Streamlit-only dashboards. Isolation Forest on fake sensors. Blockchain. Replacement CS mobile app. AI that “scores the stream” with no confirm. Notebooks as the product.

## Materials

- Factsheets: https://www.oneaquahealth.eu/app/uploads/2026/09/FactSheets_Combined_zenodo_f_citation_F_16092026.pdf
- Protocols: https://www.oneaquahealth.eu/app/uploads/2026/09/Field-Sampling-protocols-OAH_citation_Final_16092026.pdf
- FHIR IG: https://github.com/hl7-eu/oah
- Recordings: https://www.oneaquahealth.eu/project-events/ (Session 4 = FHIR)
- Official: https://www.oneaquahealth.eu/oneaquahealth-ieee-global-hackathon/
- Devpost: https://oneaquahealth-ieee-hackathon.devpost.com/
- Slack: https://join.slack.com/t/oneaquahealth-f8b4365/shared_invite/zt-4a9yfki2p-hGklHIbz4FAvy2dz7mlDYQ
- Email: oneaquahealth@ieee.org

## Contacts / today actions for the user

1. Register on Devpost if not done.
2. Start a **draft submission** so the real form is visible.
3. Join Slack.
4. Download both PDFs.
