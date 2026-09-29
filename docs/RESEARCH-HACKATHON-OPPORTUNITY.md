# OneAquaHealth IEEE Hackathon — Opportunity Research Report

> **INTERNAL / SUPERSEDED — historical research, not a description of the shipped product.** Current docs: [`docs/README.md`](README.md).

**Date:** 21 Sep 2026  
**Scope:** Research & analysis only (no production implementation)  
**Method:** Live Devpost + oneaquahealth.eu + Zenodo + hl7-eu/oah + competitor scan (Exa/Jina/gh). Local `AGENTS.md` / `WIN-PLAN.md` used as secondary notes only.

**Legend:** **[FACT]** verified from named source · **[ASSUMPTION]** inference · **[UNKNOWN]** needs human/organizer input

---

## Executive briefing

The hackathon is a **domain-judge, video-first** contest: Impact & One Health alignment is weighted **30%**, with strong pressure to plug into OAH’s existing stack (CS app, Resilience Map, GEOSSIP, City Dashboards, DSS, factsheets/protocols, FHIR IG)—not to rebuild them. Opportunity quality is **real but crowded**: Track 3’s official problem statement almost *is* “AI draft + HITL + validation,” so naive StreamWitness clones will be common. OAH already ships **DipteraCAST** (community/vector prediction AI), a **HITL Decision Support System**, and a draft **FHIR IG** (`LocationOah`, `ObservationIndicatorsOah`, `ObservationHealthMeasureOah`). StreamWitness is **viable only if it becomes infrastructure for trustworthy, factsheet-native, FHIR-conformant observations**—not a Seek/LLM photo scorer. Several non-dashboard candidates (observation integrity gates, review desks, One Health evidence briefs, CS→DSS/DipteraCAST packaging, FHIR conformance tooling) look **comparably or more defensible**. No single winner is declared; trade-offs are in §F.

---

## A. Hackathon understanding

### Mission & tagline **[FACT]**
- Theme: urban freshwater + citizen science + **One Health** (ecosystem ↔ human/animal health).
- Tagline: *“From streams to systems: turning citizen science into actionable One Health intelligence.”*
- Sources: [Devpost](https://oneaquahealth-ieee-hackathon.devpost.com/), [official page](https://www.oneaquahealth.eu/oneaquahealth-ieee-global-hackathon/).

### Official tracks (exactly 7) **[FACT]**

| Track | Challenge | Build hints |
|---|---|---|
| 1 Citizen Science UX | CS app hard to use / jargon / low participation | Guided workflows, simplified terms, data accuracy, repeat engagement |
| 2 Data-to-Insight | Hard to interpret stream data → risks / health impact | Dashboards, maps, trends, One Health summaries |
| 3 AI-Supported Assessment | Citizen obs inconsistent/error-prone | AI prompts, validation, explainable AI, **HITL** |
| 4 Awareness & Storytelling | Low awareness | Education, storytelling, personalized insights |
| 5 Community & Gamification | Low repeat engagement | Challenges, social, dashboards |
| 6 Resilience Informatics | Lack of predictive tools | Predictive dashboards, alerts, resilience |
| 7 Digital Health Standards | Fragmented data | **FHIR models**, AI agents, integration frameworks |

### Judging criteria & weights **[FACT]** — Devpost Rules

| Criterion | Weight | Score |
|---|---|---|
| Impact & Alignment with OneAquaHealth Mission | **30%** | 1–10 |
| Innovation & Creativity | 20% | 1–10 |
| Technical Implementation | 20% | 1–10 |
| Usability & UX | 15% | 1–10 |
| Feasibility & Scalability | 15% | 1–10 |

Homepage labels “Architecture / UX / Scale” are the same axes with softer names. No live pitch; video + Devpost skim first **[ASSUMPTION from local notes + typical Devpost]**; judges include domain leads (ecology, FHIR, hub tools).

### Judges (sample) **[FACT]**
Alexander Nikolov (SYNYO), Maria João Feio (OAH coordinator), Pradyumna Kodgi (Oracle), Gora Datta (FHIR), David E. González (IEEE Blockchain TC—**do not build blockchain**), Vinay Sharma, Sreekanth Reddy Panyam, George Koutalieris (ENORA—**DipteraCAST**), Harm op den Akker & Ângela Freitas (SHINE 2Europe).

### Timeline **[FACT]**
| Phase | Date |
|---|---|
| Registration opens | 1 May 2026 |
| Registration closes (pages) | 31 Aug 2026 |
| Hackathon period | **16–30 Sep 2026** |
| Judging | 1–15 Oct 2026 |
| Winners | 24 Oct 2026 (IEEE iGET) |

> Dates reflect the schedule as of 21 Sep 2026. Current Devpost deadline: **4 Oct 2026, 9:00 PM PDT (5 Oct 2026, 09:30 IST)**; judging 5–15 Oct.

**Conflict:** Devpost banner says **“Registration Still Open”** while Rules/official table say registration closed 31 Aug. Participants counter shows **950**.

### Submission requirements **[FACT]**
1. Track alignment  
2. Project description (problem, solution, users, **ecosystem + human health** impact)  
3. Demo video **3–5 minutes**  
4. Public GitHub (or equivalent) with docs  
5. Working prototype / mockup / PoC  
6. Submit before deadline  

### Required / encouraged tech & standards **[FACT]**
- AI / data platforms / **digital health standards (HL7 FHIR)** encouraged, not mandatory for every track.  
- FHIR IG: https://github.com/hl7-eu/oah · CI build: https://build.fhir.org/ig/hl7-eu/oah  
- Profiles observed: `LocationOah`, `ObservationIndicatorsOah`, `ObservationHealthMeasureOah`, `SpecimenOah`, `GroupOah`, libraries.  
- Factsheets: https://doi.org/10.5281/zenodo.20345206 (+ site PDF mirror Sep 2026).  
- Field protocols: https://doi.org/10.5281/zenodo.20344421.  
- Session recordings: https://www.oneaquahealth.eu/project-events/ (Session 4 FHIR; Sep 16 “Build with OAH”: CS App, Resilience Map, **Diptera Forecasting App**).  
- Slack invite (local docs): `https://join.slack.com/t/oneaquahealth-f8b4365/...`  
- Contact: `oneaquahealth@ieee.org`, `office@oneaquahealth.eu`.

### Datasets & scientific base **[FACT]**
- ~**100** urban stream sites across **5 cities**; DipteraCAST trained on **85 sites**, **55 Diptera taxa**.  
- Indicators: macroinvertebrates, diatoms, fish, birds, amphibians, **adult Diptera/mosquitoes**, biofilms/pathogens/AMR, hydromorphology, physico-chemistry, pharmaceuticals (detected at **91%** of sites per policy brief), well-being / health outcomes linkage protocols.  
- Policy brief: https://www.oneaquahealth.eu/app/uploads/2026/05/OneAquaHealth-Policy-Brief.pdf  

### Five cities’ role **[FACT]**
**Coimbra, Benevento, Ghent, Oslo, Toulouse** — official research cities; seed/demo against them; do not invent “official” sixth cities. Coimbra page documents channelized streams, limited official ecological monitoring, active citizen walks + focus groups—good narrative fuel.

### Expected users & ecosystem **[FACT + ASSUMPTION]**
Citizens / CS volunteers; researchers; city officers / public health & environment staff; restoration planners (DSS); OAH hub operators. Intended ecosystem: CS data → structured indicators → hub tools (dashboards, Resilience Map, GEOSSIP) → decisions / rehabilitation, with FHIR as interconnect language.

### Organizer constraints (do / don’t) **[FACT]**
- Build **on** CS app / hub tools; explore + extend.  
- Do **not** rebuild CS app, Resilience Map, GEOSSIP, City Dashboards, DSS as clones.  
- AI must not replace expert/citizen judgment where Track 3/DSS language demands HITL.  
- Blockchain judge present ≠ blockchain mandate; project messaging emphasizes FHIR/AI/CS—not Web3.

---

## B. Existing ecosystem map

### Do **not** rebuild
CS App, Resilience Map, GEOSSIP, City Dashboards, DSS, DipteraCAST core models, Play for Rivers (engagement), Health Assessment Framework (methodology).

### OAH systems

| Name | Org | URL | Target user | Problem solved | Core workflow | Data | Tech | AI | FHIR | CS | HITL | Strength | Weakness | Does NOT solve |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Citizen Science App** | OAH / SYNYO et al. | https://apps.oneaquahealth.eu/login | Citizens | Scale monitoring beyond experts | Sign up → observe/report streams → visual feedback | Geo observations, photos, stream health fields **[UNKNOWN exact schema without login]** | Web app | Unclear / limited **[UNKNOWN]** | Unclear export | Yes | Citizen is human reporter | Official channel; track 1 target | Login wall; jargon/UX called out by Track 1 | Trust scoring, FHIR packaging, officer briefs, expert adjudication |
| **Resilience Map** | OAH | https://apps.oneaquahealth.eu/resmap/ | Analysts, cities | Multi-layer ecosystem health view | Select city/site/date → explore Health & Ecosystem / Urban / Weather / EO | Biodiversity, env, pathogens, weather, satellite | Interactive map | Not primary | Unclear | Consumes research/CS data **[ASSUMPTION]** | Analyst interprets | Integrated multi-source | Not a capture/QA workflow | Field observation quality; explainable per-obs trust |
| **GEOSSIP** | OAH | https://www.oneaquahealth.eu/geossip/ → apps sites | Scientists, authorized users | Structured One Health data mgmt | Authorized entry/manage/share | Env + public health related | Platform | No (mgmt) | Unclear | Optional upstream | Expert entry | Structured research backbone | Not citizen-facing; access-limited | Public HITL assessment UX |
| **City Dashboards** | OAH | https://www.oneaquahealth.eu/city_dashboards/ | Citizens, researchers, institutions | Make research indicators accessible | Pick city/site → charts of WQ, biodiversity, pollution | Aggregated indicators | Web dashboards | No | Unclear | Indirect | Viewer interprets | Public communication | Track 2 crowded space | Capture, validation, FHIR write path |
| **Decision Support System** | OAH | https://www.oneaquahealth.eu/decision-support-system/ | Practitioners, land managers | Match impairments → rehab measures | Select indicators → impairments/stressors → measures | Indicator selections | Expert DSS | Rules/knowledge **[ASSUMPTION]** | Unclear | Can use CS-derived indicators if mapped | **Explicit HITL** (“does not replace expert judgement”) | Strong One Health→action story | Needs good indicator inputs | Generating trustworthy CS inputs |
| **DipteraCAST** | ENORA / OAH | https://www.oneaquahealth.eu/2026/07/31/oneaquahealth-dipteracast-... | Researchers, practitioners | Predict Diptera/mosquito communities from env descriptors | Upload env descriptors → multi-label ML predictions / scenarios | WQ, hydromorphology, land use, climate, RS; 55 taxa | RF, SVM, XGBoost, etc. | **Yes — core** | Planned OIH integration | Not a photo CS tool | Scenario exploration | Genuine OAH AI product; vector↔One Health | Needs structured env inputs; not citizen photo ID | Photo-based assessment; FHIR obs authoring; CS QA |
| **Health Assessment Framework** | OAH | https://www.oneaquahealth.eu/health-assessment-framework-for-urban-aquatic-ecosystems/ | Scientists, cities | Harmonize what/how to measure | Method → feed digital tools | Macroinvertebrates, WQ, habitat + birds, amphibians, adult Diptera | Methodology | No | Feeds FHIR conceptually | CS can approximate subset | Expert protocols | Defines indicator language | Not software | App UX, interoperability plumbing |
| **Factsheets** | OAH (Zenodo) | doi:10.5281/zenodo.20345206 | Stakeholders, education | Indicator literacy | Read illustrated indicator sheets | Indicator defs + methods | PDF | No | Codes map to IG **[ASSUMPTION]** | Supports CS training | N/A | Official vocabulary | Dense for lay users | Interactive guided assessment |
| **Field Sampling Protocols** | OAH (Zenodo) | doi:10.5281/zenodo.20344421 | Field teams | Comparable multi-city sampling | Site characterization → biota → vectors/microbes | Forms, physico-chem, biota, mosquitoes | PDF + forms | No | Specimens/obs | Professionals primarily | Expert QA | Comparability | Too heavy for casual CS | Lightweight CS quality gates |
| **OAH FHIR IG** | HL7 EU / OAH | https://github.com/hl7-eu/oah | Integrators | Interop for env surveillance ↔ health | Profile Location + Observations (+ Specimen, Group, Library) | Indicators + health measures | FHIR R4, FSH/SUSHI | No | **Yes** | Subject = Location | Performer required | Serious Track 7 / 3 differentiator | Draft CI-build; examples lean pollutant/disease prevalence | End-user UX; AI drafting |

### External / adjacent solutions (same jobs, different systems)

| Name | Org | URL | User | Solves | AI | FHIR | CS | Gap vs OAH |
|---|---|---|---|---|---|---|---|---|
| **FreshWater Watch** | Earthwatch | https://www.freshwaterwatch.org/ | Trained citizens | Nitrate/phosphate/turbidity kits + global map | No | No | Yes | Chemistry kits ≠ OAH One Health indicator set; no OAH FHIR |
| **iNaturalist / Seek** | California Academy / NGS | https://www.inaturalist.org/seek | Public | Photo species ID + community ID | **CV** | No | Yes | Species ID ≠ habitat/factsheet assessment; no mosquito risk packaging |
| **CrowdWater** | UZH | https://crowdwater.ch/ | Citizens | Water level, temporary streams, plastic, qualitative stream type | Game for QA | No | Yes | Hydro/plastic focus; weak One Health/FHIR |
| **eBird** | Cornell | ebird.org | Birders | Structured bird CS | Models | No | Yes | Birds only (useful but partial OAH) |
| **EPA How’s My Waterway** | US EPA | epa.gov/waterdata | Public | Official WQ exploration | No | No | Limited | Not European urban-stream One Health |
| **Commercial WQ platforms** (e.g. Aquasense-class IoT) | Vendors | various | Utilities | Sensor dashboards | Anomaly ML | Rare | No | Sensor-first; rebuild risk if faked |

---

## C. 15+ concrete problem / workflow gaps

For each: problem → user → workaround → existing → insufficient → why matters → data in/out → AI? → human? → OAH align → deadline → demo → long-term.

1. **CS observation trust is opaque to city officers**  
   Officer can’t tell which CS rows are usable. Workaround: ignore CS or ask researchers ad hoc. Resilience Map/dashboards show aggregates. Missing per-observation provenance/completeness/photo-quality flags. AI helps for completeness/photo checks; human confirms. High OAH align. Feasible. Demoable. Strong product.

2. **Factsheet language ≠ CS UI mental model**  
   Citizens misunderstand macroinvertebrate/habitat terms (Track 1). Workaround: skip fields / guess. Factsheets exist as PDFs. Insufficient without guided progressive disclosure. AI for plain-language explainers; human selects values. High. Feasible. Demoable. Medium LT (UX feature).

3. **No draft→confirm→authoritative FHIR write path for CS**  
   Integrators lack a safe status lifecycle (`preliminary`/`final`) with audit. Workaround: JSON dumps. IG profiles exist but apps don’t expose them. AI can draft coded obs; human must finalize. Very high (Tracks 3+7). Feasible. Demoable. Strong LT.

4. **DSS starved of structured CS indicator packs**  
   Restoration planner must hand-enter indicators. Workaround: expert surveys only. DSS exists. Mapping CS→DSS indicators missing. AI suggests mapping; human verifies stressors. High. Feasible. Strong demo (“CS → rehab measure”). Strong LT.

5. **DipteraCAST needs env descriptors, not random photos**  
   Vector risk prediction unused by citizens. Workaround: expert field forms. DipteraCAST exists. Packaging citizen habitat/WQ proxies into model inputs missing. AI assists descriptor extraction; human edits. High One Health. Feasible if scoped. Demoable. Strong LT.

6. **One Health “so what?” missing between stream score and health**  
   Policymaker sees biodiversity chart, not vector/well-being sentence with evidence. Policy brief exists. Dashboards weak on causal narrative. AI can draft evidence-linked briefs; human/officer owns claims. **Impact 30%**. Feasible. Excellent video. Strong LT.

7. **Expert review / adjudication of contested CS records**  
   Researchers can’t efficiently accept/reject/edit with reasons. Email/Slack. CS app capture-focused. Queue + diff + audit missing. AI triages; human adjudicates. High. Feasible. Demoable. Strong LT.

8. **Longitudinal site change without comparable protocols**  
   Repeat visits incomparable. Paper notes. Protocols heavy. Lightweight visit-to-visit diff + protocol checklist missing. AI summarizes change; human validates. Medium-high. Medium effort. Good demo. Medium LT.

9. **Photo/protocol non-compliance floods datasets**  
   Blurry bank photos, wrong angle, no scale. Manual discard. Seek helps species not habitat protocol. Quality gate missing. AI strong; human override. High Track 3. Easy demo. Medium LT.

10. **Multilingual indicator guidance across 5 cities**  
   PT/IT/NL/NO/FR/EN mismatch. English UI. Factsheets mostly one language **[UNKNOWN translations]**. AI translation risky; curated glossaries + human. High UX. Medium. Demoable. Medium LT.

11. **Cross-system identifier & Location identity**  
   Same stream site ≠ same `Location.identifier` across GEOSSIP/CS/FHIR. Spreadsheets. IG wants identifiers. Matching service missing. Rules > AI; human resolve conflicts. High Track 7. Harder. Medium demo. Strong LT infra.

12. **Pharmaceutical / pathogen signals not citizen-safe to claim**  
   Lab findings (91% pharmaceuticals) over-claimed in CS apps. Silence or hype. Need careful risk communication with uncertainty. AI drafting dangerous without templates; human required. High Impact if careful. Medium. Sensitive demo. Medium LT.

13. **Well-being observations decoupled from ecological obs**  
   HealthMeasure profile exists; rare joint capture. Separate surveys. Couple stream visit + restorative experience with ethics. Light AI; heavy human. High One Health. Feasible. Good story. Medium LT.

14. **EO / weather anomaly → investigation workflow**  
   Resilience Map shows spike; no guided “what to check on site”. Ad hoc. Map exists. Investigation checklist + CS tasking missing. AI proposes checks; human decides. Track 6-ish. Medium. Demoable. Medium LT.

15. **FAIR / provenance for hackathon-generated AI outputs**  
   Models undocumented. README claims. Session 3 FAIR emphasis. Prompt/model/version ledger missing. Process > model. High credibility with judges. Easy. Weak alone; strong combo. LT hygiene.

16. **Public health surveillance handoff for Diptera signals**  
   Policy asks integrate Diptera into surveillance. Email PDFs. No structured alert packet. AI summarizes; epidemiologist confirms. High. Hard without partners. Weak deadline unless simulated. Strong LT.

17. **Gamified engagement without corrupting data quality**  
   Track 5 points vs accuracy tradeoff. Badges only. Need quality-weighted reputation. AI gaming risk; human rules. Medium. Feasible. Risk of “toy.” Weak LT unless tied to trust.

18. **Open export of CS data for third-party innovators**  
   Hackathon teams can’t build without login/sample. Screenshots. Need synthetic/realistic fixtures + schema docs. No AI needed. High for ecosystem. Easy. Meta. LT enabler.

---

## D. 15+ candidate products

*(StreamWitness included; not privileged.)*

1. **StreamWitness** — Photo + factsheet checklist → AI **DRAFT** indicators → citizen confirm → FHIR Location/Observation + One Health sentence. User: citizen (+ reviewer). Pain: inconsistent CS. Alt: CS app / Seek. Innovation: OAH-vocab + HITL + FHIR. AI: draft only. Human: authority. Arch: upload → vision/LLM isolated → schema validate → audit → FHIR. FHIR: core. One Health: sentence + indicators. Demo: 90s photo→confirm→JSON. Realistic: yes. LT: depends on differentiation. Risks: crowded Track 3; wrapper; DipteraCAST overlap narrative.

2. **TrustGate (Observation Integrity Service)** — Scores completeness, photo protocol compliance, geolocation sanity; outputs trust labels + block reasons before any “final” FHIR. User: CS platform / reviewers. Pain: unusable CS rows. Alt: manual discard. Innovation: quality as first-class product. AI: QA classifiers/LLM checks. Human: override. Data: photos+fields→trust report. Arch: rules engine + optional AI + audit. FHIR: extensions / `Observation.status`. Demo: reject bad photo, accept good. Realistic: high. LT: strong infra. Risks: “just validation forms.”

3. **ReviewDesk** — Expert queue: accept / edit / reject with coded reasons; disagreement threads; export confirmed bundle. User: researchers. Pain: inbox chaos. Alt: spreadsheets. Innovation: adjudication workflow. AI: triage + suggested edits. Human: final. FHIR: write on confirm. Demo: two conflicting reports. Realistic: high. LT: strong. Risks: looks like generic CMS.

4. **EvidenceBrief** — Multi-source pack (CS confirmed + Resilience/EO summary + policy brief citations) → officer one-pager with uncertainty. User: city officer. Pain: dashboards without action narrative. Alt: manual slide decks. Innovation: evidence-linked One Health translation. AI: drafting. Human: sign-off. FHIR: read obs. Demo: Coimbra brief. Realistic: high. LT: strong Impact. Risks: Track 2 dashboard clone if map-heavy.

5. **DSS Feed Packager** — Maps confirmed CS indicators → DSS input selections + stressor hypotheses for human. User: restoration planner. Pain: DSS empty. Alt: expert-only. Innovation: CS→rehab bridge. AI: mapping assist. Human: DSS HITL. Demo: CS → recommended measures. Realistic: medium (need DSS I/O knowledge). LT: excellent alignment. Risks: DSS API closed **[UNKNOWN]**.

6. **DipteraPrep** — Guides citizen/field user to collect **env descriptors** DipteraCAST needs; HITL confirm; optional call/sim to prediction. User: practitioners/citizens advanced. Pain: AI model unreachable from CS. Alt: expert spreadsheet. Innovation: complement not clone DipteraCAST. AI: optional secondary. Human: descriptor truth. Demo: descriptors → predicted vector community. Realistic: medium. LT: high One Health. Risks: competing with ENORA judge’s product if presented as replacement.

7. **FHIR Forge Lite (OAH Conformance Workbench)** — Validate/transform JSON into `LocationOah` / `ObservationIndicatorsOah` / HealthMeasure; show diffs vs profiles. User: integrators / Track 7. Pain: IG hard. Alt: hand FSH. Innovation: OAH-specific tooling. AI: map free text→codes. Human: code choice. Demo: invalid→valid resource. Realistic: high for skilled solo. LT: infra. Risks: “not a product” for Impact judges; Gora Datta may love it.

8. **SiteDossier** — Longitudinal site notebook: visits, photos, confirmed obs, change summary. User: city + researchers. Pain: no memory. Alt: folders. Innovation: time as first-class. AI: change narrative. Human: confirm change claims. Demo: before/after channelization story (Coimbra). Realistic: medium. LT: good. Risks: CMS-y.

9. **Anomaly Investigation Copilot** — From Resilience Map-like alert → checklist of field checks + CS tasking template. User: analyst. Pain: alert without action. Alt: email. Innovation: close loop Track 6. AI: suggest hypotheses. Human: investigate. Demo: spike → task list. Realistic: medium without live APIs. LT: medium. Risks: fake Isolation Forest smell if sensors invented.

10. **Glossary Guide (Track 1)** — Progressive, illustrated, multilingual factsheet UX over CS fields (companion, not replacement app). User: citizen. Pain: jargon. Alt: PDF. Innovation: OAH-native pedagogy. AI: adaptive help. Human: answers. Demo: confused→correct macroinvertebrate class. Realistic: high. LT: feature. Risks: weak Innovation/Technical.

11. **WellbeingLink** — Couples ecological visit with OAH HealthMeasure fields + ethics consent. User: citizen / health researcher. Pain: env-health split. Alt: separate surveys. Innovation: FHIR HealthMeasure usage. AI: minimal. Human: consent & self-report. Demo: walk → dual Observation. Realistic: high. LT: research. Risks: medical/ethics sensitivity; shallow AI story for Track 3.

12. **Provenance Ledger** — Versioned prompts, model IDs, human edits, timestamps as first-class audit API. User: auditors, judges, cities. Pain: AI black boxes. Alt: logs. Innovation: trust architecture. AI: none required. Human: center. Demo: show edit diff killed hallucination. Realistic: high as module. LT: strong. Risks: incomplete product alone.

13. **Crosswalk ID Resolver** — Match GEOSSIP site IDs ↔ CS ↔ FHIR Location. User: data engineers. Pain: fragmented sites. Alt: Excel VLOOKUP. Innovation: Location identity layer. AI: fuzzy match. Human: approve merges. Demo: merge duplicates. Realistic: medium. LT: critical infra. Risks: dry demo; needs real IDs.

14. **RiskComm Templates** — Safe messaging for pharmaceuticals/vectors/AMR with uncertainty language + sources. User: communications / officers. Pain: overclaim. Alt: silence. Innovation: safety rails. AI: fill templates. Human: approve. Demo: bad vs good claim. Realistic: high. LT: medium. Risks: “content not software.”

15. **Synthetic OAH Fixture Kit + Sandbox API** — Realistic 5-city sample observations, photos, FHIR examples for builders. User: hackathon/ecosystem. Pain: login walls. Alt: invent data. Innovation: ecosystem enablement. AI: optional generation with labels. Human: curation. Demo: openAPI + fixtures. Realistic: high. LT: community. Risks: Impact judges want citizen outcomes not DX.

16. **Collaborative Stream Walk Mode** — Multi-participant same-site session with role split (photo, habitat, Diptera, wellbeing) + merge. User: community groups (Coimbra walks). Pain: single-user forms. Alt: paper. Innovation: collaborative CS. AI: merge conflicts assist. Human: lead. Demo: family walk. Realistic: medium. LT: engagement. Risks: Track 5 toy; needs mobile.

17. **Play-adjacent Stewardship Tracker** — Light commitments/restoration follow-ups tied to DSS measures (not game points). User: municipalities + citizens. Pain: recommendations die. Alt: PDFs. Innovation: action tracking. AI: reminders. Human: verify completion. Demo: measure assigned→done. Realistic: medium. LT: good. Risks: needs city partner.

---

## E. Competitive destruction

| Candidate | “Already exists?” | Weekend wrapper? | Real capability? | vs OAH systems | <90s unique value? | Useful without AI? | Safe if AI wrong? | 6-month engineerable? | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| StreamWitness | Seek + CS + Track 3 text | **High risk** if GPT-vision→score | Only if FHIR+audit+vocab deep | Must not replace CS; DipteraCAST is “the AI” | Only if confirm≠draft crystal clear | Checklist alone = Track 1 | Yes if draft-only | Yes | **Conditional keep / else kill** |
| TrustGate | Partial in CrowdWater game | Medium | Yes | Fills CS quality hole | Yes (reject bad photo) | Rules-first yes | Yes | Yes | **Strong** |
| ReviewDesk | Generic review tools | Low if OAH-coded reasons | Yes | Extends CS | Yes | Yes | Yes | Yes | **Strong** |
| EvidenceBrief | Consultancies | Medium | Workflow yes | Complements dashboards | Yes if one Coimbra page | Template yes | Cite-or-refuse | Yes | **Strong** |
| DSS Packager | Nowhere public | Low | Depends on DSS I/O | Explicit complement | Excellent | Mapping tables | Human DSS | Medium | **Strong if API known** |
| DipteraPrep | DipteraCAST itself | High if “we predict mosquitoes” | Only as **input prep** | Must complement ENORA | Yes if framed as prep | Forms yes | Don’t auto-claim disease | Medium | **Keep only as feeder** |
| FHIR Workbench | IG publisher / Forge | Medium | Real for Track 7 | Uses IG | Medium (geeky) | Yes | N/A | Yes | **Niche / judge-dependent** |
| SiteDossier | Folders / ArcGIS | Medium | Mild | — | Medium | Yes | Yes | Yes | Weak alone |
| Anomaly Copilot | Many AI ops tools | **High** if fake sensors | Weak without data | Resilience Map exists | Medium | Checklists | Yes | Medium | **Kill Isolation Forest variants** |
| Glossary Guide | Factsheet PDF | Medium | UX | Track 1 | Medium | Yes | Yes | Yes | Weak |
| WellbeingLink | Surveys | Low AI | Real One Health | HealthMeasure profile | Medium | Yes | Ethics | Medium | Specialty |
| Provenance | MLOps | Low | Architecture | FAIR session | Medium | Yes | Core | Yes | Module not product |
| ID Resolver | MDM tools | Low | Infra | GEOSSIP/CS | Weak video | Yes | Yes | Hard | Kill for solo deadline unless data |
| RiskComm | Comms shops | Medium | Soft | Policy brief | Medium | Templates | Mandatory | Easy | Kill alone |
| Fixture Kit | Hackathon DX | Low | Ecosystem | — | Weak Impact | Yes | Label synthetic | Easy | Kill as main |
| Collab Walk | Event apps | Medium | Nice | Coimbra walks | Medium | Yes | Yes | Medium | Secondary |
| Stewardship Tracker | Project mgmt | Medium | Needs partners | DSS | Medium | Yes | Yes | Medium | Kill without partner |

**StreamWitness kill criteria (clear):**
- Demo scores the stream without mandatory edit/confirm.  
- FHIR is pretty-printed JSON not aligned to OAH profiles/value sets.  
- No audit of AI vs human.  
- Narrative competes with DipteraCAST (“our AI predicts mosquitoes”).  
- Generic habitat adjectives instead of factsheet indicators.

---

## F. Shortlist (~5) — no declared winner

### 1) TrustGate — Observation Integrity Service
- **Strongest evidence:** Track 3 text centers inconsistent/error-prone CS; CrowdWater shows QA games work; OAH protocols imply compliance matters.  
- **Strongest weakness:** May look “not flashy AI.”  
- **Biggest unknown:** Exact CS app validation rules / export.  
- **Dangerous assumption:** Judges value data quality over dashboards.  
- **Validation:** Watch Session recordings; use CS app; ask Slack what ruins CS data.  
- **Difficulty:** Medium.  
- **Novelty:** Moderate (workflow), not claim “never done.”  
- **OAH align:** High.  
- **Demo:** Strong.  
- **LT:** Strong infra product.

### 2) EvidenceBrief — One Health officer brief
- **Evidence:** Impact 30%; policy brief links degradation↔mortality/vectors; Track 2 problem language.  
- **Weakness:** Easy to slide into generic dashboard.  
- **Unknown:** Officer actual decision cadence in 5 cities.  
- **Dangerous assumption:** A paragraph changes decisions.  
- **Validation:** Interview / Slack city contacts; read Coimbra focus-group notes.  
- **Difficulty:** Medium.  
- **Novelty:** Packaging, not algorithms.  
- **OAH align:** Very high if cited.  
- **Demo:** Excellent for video.  
- **LT:** Advisory product.

### 3) ReviewDesk — HITL adjudication
- **Evidence:** Track 3 HITL; DSS already models “don’t replace experts.”  
- **Weakness:** Feels enterprise-y.  
- **Unknown:** Who reviews CS today.  
- **Dangerous assumption:** There is a reviewer role at all.  
- **Validation:** Ask OAH how CS QC works.  
- **Difficulty:** Medium.  
- **Novelty:** Domain-coded reject reasons.  
- **OAH align:** High.  
- **Demo:** Strong.  
- **LT:** Strong.

### 4) DSS Feed Packager / DipteraPrep (pick one feeder)
- **Evidence:** Official tools need structured inputs; Sep 16 session highlights CS + Resilience + Diptera app.  
- **Weakness:** Dependency on closed APIs; DipteraPrep can offend if framed as competing AI.  
- **Unknown:** Public I/O contracts.  
- **Dangerous assumption:** Can integrate without partner access.  
- **Validation:** Email organizers; inspect webinar PDF; simulate with fixtures.  
- **Difficulty:** Medium–high.  
- **Novelty:** Bridge architecture.  
- **OAH align:** Maximal if complementary.  
- **Demo:** Very strong “extend, don’t rebuild.”  
- **LT:** Excellent.

### 5) StreamWitness (only if hardened)
- **Evidence:** Literal Track 3; FHIR IG exists; factsheets vocabulary.  
- **Weakness:** Highest clone density; Seek/LLM wrapper optics; DipteraCAST already “OAH AI.”  
- **Unknown:** Whether vision can meaningfully draft OAH indicators from casual photos (often **no**).  
- **Dangerous assumption:** Photo ⇒ ecological truth.  
- **Validation:** Blind test: can ecologists accept AI drafts? If not, demote vision to quality/assist only.  
- **Difficulty:** Medium.  
- **Novelty:** Low unless FHIR+audit+factsheet fidelity are exceptional.  
- **OAH align:** High if done right.  
- **Demo:** High.  
- **LT:** Medium unless becomes TrustGate+FHIR platform.

### Trade-offs
| Axis | TrustGate | EvidenceBrief | ReviewDesk | Feeder (DSS/Diptera) | StreamWitness |
|---|---|---|---|---|---|
| Impact story | Data trust | **Best** One Health narrative | Process trust | Action/rehab/vectors | Assessment |
| Innovation optics | Subtle | Medium | Medium | High if bridge | Crowded |
| Technical depth | Rules+AI | RAG/citations | Workflow | Integration | Vision+FHIR |
| Demo clarity | High | **Highest** | High | High | High |
| Clone risk | Lower | Medium | Lower | Lower | **Highest** |
| Partner dependency | Low | Low–med | Med | **High** | Low |
| Solo feasibility | High | High | High | Med | High |

**Human decision:** Optimize for Impact narrative vs clone-risk vs partner access. A production-grade path many engineers could continue is **TrustGate + FHIR finalize + EvidenceBrief** as modules—with StreamWitness UI as one client, not the whole thesis.

---

## G. Unknowns requiring human research

1. CS app: field schema, photo requirements, export/API, QC process today.  
2. Whether DSS / DipteraCAST / Resilience Map expose any hackathon APIs or sample files.  
3. Authoritative OAH indicator value sets ↔ CS form codes (ConceptMaps in IG).  
4. City officer persona: who decides what, weekly?  
5. Ethics constraints on well-being / health claims in demos.  
6. Preferred track politics: is Track 7 scored differently by Gora Datta?  
7. Gallery of prior/peer submissions (unpublished)—monitor Devpost.  
8. Factsheet list exact citizen-usable subset vs lab-only indicators.  
9. Multilingual assets availability.  
10. Whether `Observation.status` draft pattern is acceptable vs only `#final` in profile (profile shows `status = #final`—tension with DRAFT UX) **[FACT: profile pins final]** → may need separate resource or extension for drafts.

---

## H. Prioritized next research questions (before implementation)

1. Create Devpost **draft submission** to see form fields.  
2. Login CS app; document every field & photo prompt; export anything possible.  
3. Read full Factsheets + Protocols PDFs; list **citizen-safe** vs **lab-only** indicators.  
4. Clone/build against `hl7-eu/oah` examples; list mandatory elements & value sets; resolve draft vs `status=final`.  
5. Watch Session 4 (FHIR) + Sep 16 hub tools recording; download Aug 27 PDF.  
6. Ask Slack: “What is the #1 data quality failure in the CS app?”  
7. Blind photo study: 20 stream photos → can AI draft factsheet fields usefully?  
8. Confirm DipteraCAST/DSS access path; if none, design **fixture-based** feeders.  
9. Pick shortlist of 2; write kill criteria; only then architecture spike.

### Architecture principles for eventual build (do not implement now)
Modular boundaries; typed interfaces between ingest / AI / review / FHIR / UI; env-based config; no secrets in git; **isolated AI layer** with versioned prompts/models; schema validation before persistence; migrations; replaceable providers (LLM, DB, object storage, FHIR server, frontend); audit log as append-only; draft ≠ authoritative; synthetic fixtures; CI that validates FHIR examples against profiles.

---

## Source index (primary)

- https://oneaquahealth-ieee-hackathon.devpost.com/ (+ `/rules`)  
- https://www.oneaquahealth.eu/oneaquahealth-ieee-global-hackathon/  
- https://www.oneaquahealth.eu/project-solutions/ · geossip · city_dashboards · decision-support-system · health-assessment-framework · research-cities/* · project-events  
- https://www.oneaquahealth.eu/2026/07/31/oneaquahealth-dipteracast-...  
- https://www.oneaquahealth.eu/app/uploads/2026/05/OneAquaHealth-Policy-Brief.pdf  
- https://github.com/hl7-eu/oah · https://build.fhir.org/ig/hl7-eu/oah  
- Zenodo factsheets doi:10.5281/zenodo.20345206 · protocols doi:10.5281/zenodo.20344421  
- FreshWater Watch, Seek/iNaturalist, CrowdWater (competitor scan)  

**Local secondary only:** `AGENTS.md`, `docs/WIN-PLAN.md`, `docs/SUBMISSION.md` (some claims outdated vs live Devpost).
