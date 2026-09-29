# Product Validation — OneAquaHealth IEEE Global Hackathon

> **INTERNAL / SUPERSEDED — historical research, not a description of the shipped product.** Current docs: [`docs/README.md`](README.md).

**Date:** 21 Sep 2026  
**Scope:** Research + hostile validation only. **No implementation.**  
**Method:** Primary sources (Devpost, oneaquahealth.eu, Zenodo PDFs via `pdftotext`/`pypdf`, `hl7-eu/oah` clone, HL7 FHIR R4 docs, competitor sites, Exa/Jina). Local `AGENTS.md` / `WIN-PLAN.md` / `SUBMISSION.md` / `docs/RESEARCH-HACKATHON-OPPORTUNITY.md` treated as **challenged priors**, not authority.  
**Legend:** **[FACT]** cited primary · **[INFERENCE]** reasoned from facts · **[UNKNOWN]** needs organizer/domain confirmation  

**Philosophy applied:** Production product whose first release is a hackathon submission. Prefer technical *depth* demanded by the problem over decorative complexity. Optimize jointly for Impact 30% / Innovation 20% / Technical 20% / UX 15% / Feasibility 15%.

---

## Executive verdict (non-binding)

Prior opportunity research correctly identified overcrowding in Track 3 and the value of trust, review, FHIR, and officer briefs. It **under-challenged** the scientific legitimacy of “photo → AI drafts OAH factsheet indicators.” Official factsheets are overwhelmingly **lab/expert protocols**; the citizen-friendly vocabulary lives mainly in the **field form (protocols Annex I)** and a few visual surveys—not in casual phone photos of “stream health.”

**Combined mega-pipeline** (citizen obs → AI quality assessment → AI draft → confirm → trust score → expert review → FHIR → One Health brief) is **not one coherent product** unless aggressively pruned. A **limited pipeline** survives: *structured citizen/protocol-lite capture → deterministic(+optional AI) quality flags → human authority → FHIR finalize (status final only) → optional evidence-grounded officer brief*. Stages that only sound sophisticated (composite AI trust scores, photo-inferred BMWP/Diptera risk, auto-diagnosis) should be removed.

**No single winner is declared.** Three architectures remain serious (Section L).

### Material contradictions vs `docs/RESEARCH-HACKATHON-OPPORTUNITY.md` and `WIN-PLAN.md`

| Prior claim | Challenge | Evidence |
|---|---|---|
| StreamWitness checklist ≈ habitat + macros + Diptera + WQ + well-being as factsheet-native | **Partially false.** Official factsheet collection lists **11 indicators (I–XI)**; habitat/hydromorphology and physico-chem are in **protocols / field form**, not the factsheet TOC. Well-being/disease prevalence is FHIR HealthMeasure / epidemiological codes, **not** a factsheet. | Factsheets PDF p.3 TOC; Protocols Annex I; `observation-health-measure-oah.fsh` |
| Vision/LLM can draft meaningful OAH indicator values from citizen photos | **Mostly indefensible** for official indicators (diatoms, ARG, pathogens, electrofishing, CO₂ Diptera traps, etc.). Photo may assist **protocol compliance / macrophyte-riparian categories / invasive plants / foam-colour-smell**. | Factsheets measurement sections; Protocols materials lists |
| Zenodo factsheets doi `20345206` | PDF cites **`https://doi.org/10.5281/zenodo.20345207`**; site mirror matches Sep 2026 PDF. Treat **20345207** as the cited version; 20345206 may be alias/prior. | Factsheets PDF citation page |
| Bundle TrustGate + Review + FHIR + EvidenceBrief as natural product | **Coherent only as limited pipeline** with shared domain object “confirmed observation.” Four UIs / four personas is kitchen sink. | Section B |
| DipteraCAST feeder as peer shortlist item | Valid **bridge**, but high partner/API unknown; framing as competing AI risks ENORA judge (Koutalieris). | DipteraCAST article; Devpost judges |

---

## A. Candidate decomposition

### A1. TrustGate (Observation Integrity Service)

| Dimension | Definition |
|---|---|
| **User** | CS platform operator / scientific data curator for OAH cities who must decide which citizen (or semi-trained) rows enter analyses, dashboards, or FHIR export—not “everyone.” |
| **Trigger** | New observation submitted (photo + structured fields) or batch import before publish. |
| **Current workflow** | Manual eyeballing, ad-hoc discard, or silent acceptance into aggregates. **[UNKNOWN]** exact CS-app QC today (login wall). |
| **Pain** | Officers/researchers cannot tell which CS rows are protocol-complete, in-range, geolocated, or photo-compliant; bad rows poison trust in *all* CS. |
| **Input** | Structured fields (ideally protocols Annex I subset), optional photo(s), GPS/time, city/site id, submitter id. |
| **Processing** | Prefer **deterministic rules + flags** (required fields, categorical vocab, ranges, duplicate proximity, image blur/exposure/framing heuristics). Optional AI only for photo protocol checks / OCR of gauges—not ecological “score.” |
| **Output** | Machine-readable **quality flag set** + human-readable fail reasons; gate states: `reject` / `needs_human` / `pass_to_review_or_finalize`. **Not** a single 0–100 “trust score” unless scientifically justified (prefer CrowdWater-style multi-rater or explicit flags). |
| **Authority** | Rules own hard rejects; human overrides soft flags. Never auto-authoritative ecology. |
| **Frequency** | Per submission; high volume if CS scales. |
| **Failure consequence** | False reject → lost engagement; false accept → bad DSS/map decisions and reputational damage to OAH CS. |
| **Existing alternative** | CrowdWater game for water-level QA **[FACT]** (PLOS One 2019); iNaturalist community ID; FreshWater Watch kit protocols; OAH CS app (schema unknown). |
| **Differentiation** | OAH **factsheet/protocol vocabulary** + FHIR readiness + One Health-aware “do not claim” gates (no pathogen/diagnosis from photo). |
| **OAH connection** | Directly addresses Track 3 “inconsistent/error-prone” problem statement **[FACT]** Devpost. Feeds Resilience Map / dashboards / DSS with cleaner inputs without rebuilding them. |
| **Post-hackathon value** | Infrastructure product; embeddable microservice/library beside CS app. |

### A2. EvidenceBrief (One Health officer brief)

| Dimension | Definition |
|---|---|
| **User** | Municipal environment / public-health / restoration officer in Coimbra, Benevento, Ghent, Oslo, or Toulouse preparing a short decision note—not a tourist. |
| **Trigger** | Confirmed site packet ready (or weekly city digest); rehab planning meeting; vector-surveillance question. |
| **Current workflow** | Skim City Dashboards / Resilience Map / policy PDFs; ask researchers; improvise slides. |
| **Pain** | Aggregates exist; **actionable, evidence-linked One Health narrative with uncertainty** does not ship with each usable observation set. Impact criterion is 30%. |
| **Input** | Confirmed indicators (flags + sources), optional EO/dashboard summaries (read-only), citations from OAH policy brief/factsheets. |
| **Processing** | Prefer **templates + citation rules**; generative AI only to fill slots with refuse-if-missing. No causal diagnosis. |
| **Output** | 1-page brief: what was observed, quality status, ecological implication (cited), human/animal health relevance (cited, non-diagnostic), uncertainty, next investigation, responsible authority. |
| **Authority** | Officer (or designated scientist) must approve publish/share. |
| **Frequency** | Event-driven or weekly; low volume, high stakes. |
| **Failure consequence** | Alarmist or unsupported claims → political/legal harm; empty fluff → ignored. |
| **Existing alternative** | Consultancies; OAH Policy Brief (static); dashboards without decision narrative. |
| **Differentiation** | Grounded in **confirmed OAH indicators + official citations**, not LLM weather chatter. |
| **OAH connection** | Policy brief links degradation ↔ mortality/vectors/pharma/IAP **[FACT]**; DSS already HITL for rehab—brief is upstream “why act.” |
| **Post-hackathon value** | Advisory layer over hub data; strong Impact narrative. |

### A3. ReviewDesk (Expert adjudication)

| Dimension | Definition |
|---|---|
| **User** | Environmental scientist / trained CS coordinator / city technical staff adjudicating contested or flagged records. |
| **Trigger** | TrustGate `needs_human`; disagreement between citizen and AI assist; duplicate site conflict. |
| **Current workflow** | Email/Slack; spreadsheets; **[UNKNOWN]** whether a formal reviewer role exists in OAH ops. |
| **Pain** | No coded accept/edit/reject with reason codes and audit trail → cannot defend CS in scientific or FHIR contexts. |
| **Input** | Flagged observation + media + prior flags + draft values. |
| **Processing** | Queue + diff UI + coded reasons; optional AI triage (priority only). |
| **Output** | Adjudicated record + audit; unlock FHIR finalize / brief eligibility. |
| **Authority** | Expert (or designated role) is final for scientific acceptance; citizen remains author of self-report fields. |
| **Frequency** | Subset of submissions; depends on gate strictness. |
| **Failure consequence** | Bottleneck kills CS; rubber-stamping recreates TrustGate failure. |
| **Existing alternative** | Generic CMS; iNaturalist research-grade votes; CrowdWater game votes. |
| **Differentiation** | OAH-coded reject reasons tied to protocols (wrong reach length, missing A/P/E, no permit for amphibians, etc.). |
| **OAH connection** | Mirrors DSS language: structures expert judgement, does not replace it **[FACT]** DSS page. |
| **Post-hackathon value** | Ops tooling; needs real reviewer personas to stay alive. |

### A4. DSS / DipteraCAST feeder

| Dimension | Definition |
|---|---|
| **User** | Restoration planner (DSS) or practitioner preparing **environmental descriptors** for DipteraCAST—not casual walkers. |
| **Trigger** | Need rehab measure shortlist; need Diptera community prediction / scenario. |
| **Current workflow** | Hand-enter indicators into DSS; separately assemble env descriptors for DipteraCAST upload. |
| **Pain** | Confirmed CS/field data does not package into tool I/O; official AI (DipteraCAST) unused by CS channel. |
| **Input** | Confirmed structured indicators / site characterization; **not** random photos as model input. |
| **Processing** | Deterministic mapping tables CS/protocol fields → DSS selections / DipteraCAST descriptor schema; HITL edit. |
| **Output** | Tool-ready pack (JSON/CSV) + human checklist of remaining required fields; optional simulated prediction if API unavailable. |
| **Authority** | Planner/practitioner; DipteraCAST/DSS remain authoritative engines. |
| **Frequency** | Project-based. |
| **Failure consequence** | Wrong mapping → bad rehab advice or vector scenarios; framing as “our mosquito AI” antagonizes ENORA. |
| **Existing alternative** | Manual entry; expert surveys that already fed the 85-site training set **[FACT]** DipteraCAST article. |
| **Differentiation** | Explicit **complement** (“feed, don’t replace”) to OAH AI and DSS. |
| **OAH connection** | Maximal “extend don’t rebuild”; DipteraCAST needs WQ, hydromorphology, land use, climate, RS **[FACT]**. |
| **Post-hackathon value** | High if I/O contracts exist; otherwise stays fixture-demo. |

### A5. Hardened StreamWitness (citizen HITL assessment client)

| Dimension | Definition |
|---|---|
| **User** | Trained or semi-trained citizen / CS volunteer at an OAH city stream, guided to fill **protocol-lite** fields—not an untrained tourist claiming BMWP from a selfie. |
| **Trigger** | Field visit / organised walk. |
| **Current workflow** | OAH CS app (login-walled) **[FACT]**; paper; Seek for species only. |
| **Pain** | Track 1 jargon; Track 3 inconsistency; no clear DRAFT→human→authoritative FHIR path in public tools. |
| **Input** | City/site, photos (evidence), **categorical protocol fields** (macrophytes A/P/E, riparian cover bins, hydromorph P/E/A, foam/colour/smell), optional Merlin bird list; **not** lab indicators. |
| **Processing** | Form-first; AI optional for (a) photo quality, (b) plain-language glosses, (c) suggested categorical labels with low confidence—**never** lab/index inference. Human confirm mandatory. |
| **Output** | Citizen-confirmed draft record → handoff to TrustGate/Review/FHIR modules. |
| **Authority** | Human citizen for self-report; system never auto-finalizes FHIR. |
| **Frequency** | Per visit. |
| **Failure consequence** | If vision “scores the stream,” product collapses scientifically and as Track 3 clone. |
| **Existing alternative** | CS app; FreshWater Watch kits; CrowdWater stream-type; Seek. |
| **Differentiation** | Only if **protocol-native fields + audit + OAH FHIR profiles + explicit non-claims**—not “ChatGPT looks at river.” |
| **OAH connection** | Literal Track 3 wording **[FACT]**; high clone density. |
| **Post-hackathon value** | Client of trust/FHIR platform; weak as standalone if undifferentiated. |

---

## B. Combined-product hypothesis

**Prior hypothesis:** TrustGate + Review workflow + FHIR finalization + EvidenceBrief (+ citizen input client) = one product.

### Transition validation (hypothesis pipeline)

| Transition | Why it exists | Who needs it | Data change | AI vs rules | Human required? | FHIR? | OAH already? | Keep? |
|---|---|---|---|---|---|---|---|---|
| Citizen obs → validation | CS noise | Curator/officer | Add flags | Rules first | Override | No | Partial unknown | **Keep** |
| Validation → “quality assessment” as separate AI stage | Sounds smart | Nobody if flags exist | Duplicate | AI redundant | No | No | No | **Remove** as separate stage |
| → AI draft of ecological score | Track 3 temptation | Demo video | Invented values | AI high risk | Yes | Tempting misuse | DipteraCAST is real AI elsewhere | **Remove** for lab indicators; **narrow** for categorical visual fields only |
| → human confirm | Track 3 / ethics | Citizen/expert | Draft→confirmed | N/A | **Yes** | Not yet | DSS philosophy | **Keep** |
| → trust/provenance | Defend use | Auditor/officer | Provenance events | Ledger rules | For overrides | Provenance resource optional | FAIR session | **Keep as flags+audit**, not composite score |
| → expert review | Scientific acceptance | When flagged | Adjudicated | Triage optional | **Yes if gated** | Still not final until confirm | Unknown role | **Keep optional queue**, not every row |
| → FHIR finalize | Interop Track 7/3 | Integrator | Domain→`Observation` `status=final` | Deterministic map | Confirm before write | **Yes** | IG exists; apps don’t expose | **Keep** |
| → One Health interpretation | Impact 30% | Officer | Brief object | Templates > LLM | Approve | Read obs | Policy brief static | **Keep optional** |
| → officer brief UI as always-on | Same | Officer | Presentation | Same | Same | No | Dashboards | **Keep as view**, not separate product mandatory |

### Conclusion on coherence

**Verdict: limited coherent pipeline — not kitchen sink if pruned; kitchen sink if shipped as four personas + photo-AI scoring + composite trust + DSS + DipteraCAST + dashboards.**

Evidence: Official tools already cover capture (CS), explore (Resilience Map / dashboards), rehab (DSS), vector prediction (DipteraCAST), methodology (framework/factsheets/protocols), interop (FHIR IG draft). The **missing wedge** is trustworthy **protocol-aligned observation lifecycle** ending in conformant FHIR and optional decision narrative—not another assessment AI.

Natural product object: **`ConfirmedObservationPacket`** (fields + media + flags + audit + optional FHIR Bundle). TrustGate writes flags; ReviewDesk mutates packet; FHIR exporter emits only when confirmed; EvidenceBrief reads packets. StreamWitness is **one ingest client**. DSS/DipteraCAST feeders are **export adapters**.

---

## C. User journey validation

### Personas

#### 1. Citizen / citizen scientist (must interact for ingest-oriented products)

- **Goal:** Report a stream visit usefully without pretending to be a lab.  
- **Existing:** CS app login; organised walks (e.g. Coimbra narrative in prior city pages).  
- **Frustration:** Jargon; unclear what photos prove; no feedback whether data was usable.  
- **Product interaction:** Protocol-lite form + photo evidence + confirm; see flags (“needs clearer bank photo”).  
- **Expected result:** Confirmation receipt; optional “your report is under review.”  
- **Trust requirement:** Know AI suggestions are DRAFT; know what they must not claim.  
- **Should NOT see:** Raw disease prevalence FHIR, ARG qPCR, other citizens’ PII, composite “trust score” gamified to cheat.  
- **Authorized actions:** Create/edit own draft; confirm own fields; withdraw.

#### 2. Scientific reviewer / environmental expert (must interact only if ReviewDesk or lab-grade claims)

- **Goal:** Accept/reject/edit with reasons so data can enter science/DSS.  
- **Existing:** Email; field campaigns with CEN standards.  
- **Frustration:** Inbox chaos; citizens invent taxa.  
- **Product interaction:** Queue of flagged packets; coded decisions.  
- **Expected result:** Adjudicated packet ready for FHIR/export.  
- **Trust:** Full audit; model versions if AI assisted.  
- **Should NOT see:** Needless medical diagnosis UIs.  
- **Authorized:** Accept/edit/reject; request re-sample; never silently alter without audit.

#### 3. City officer / decision-maker (must interact for EvidenceBrief; optional for TrustGate)

- **Goal:** Decide whether to investigate, restore, or brief public health—fast, defensible.  
- **Existing:** Dashboards, policy PDFs, meetings.  
- **Frustration:** Charts without “so what” + uncertainty.  
- **Product interaction:** Read/approve brief; filter by quality flags.  
- **Expected result:** 1-pager with citations and next step.  
- **Trust:** Sources visible; no alarmism.  
- **Should NOT see:** Model logits; unfinished drafts; citizen contact details.  
- **Authorized:** Approve/share brief; request expert review; not edit raw ecology without role.

#### 4. Data/integration engineer (must interact for FHIR-first; otherwise secondary)

- **Goal:** Emit/consume `LocationOah` + `ObservationIndicatorsOah` valid against IG.  
- **Existing:** Hand-built JSON; IG CI-build.  
- **Frustration:** Draft UX vs `status = #final` pattern; temporary code system.  
- **Product interaction:** Validation report; Bundle download; concept map.  
- **Expected result:** Validator-clean resources + Provenance of confirmation.  
- **Trust:** Profile conformance logs.  
- **Should NOT see:** Needless citizen UX chrome.  
- **Authorized:** Export/transform; not scientifically “confirm.”

### Smallest coherent user ecosystem

**Minimum viable:** (1) **Citizen** + (2) **system rules** + (3) **either officer OR reviewer** depending on thesis.

| Product thesis | Personas that MUST interact | Kill if… |
|---|---|---|
| TrustGate + FHIR finalize | Citizen (or import) + curator/reviewer override | No human authority path |
| EvidenceBrief | Officer + upstream confirmed data (can be fixtures) | No evidence grounding |
| ReviewDesk | Reviewer (+ ingest source) | No real reviewer role exists |
| Feeder | Planner/practitioner | No descriptor schema |
| Hardened StreamWitness | Citizen (+ optional reviewer) | Tries to serve officer+engineer+reviewer in one hero UI |

**Do not build four separate polished UIs in one hackathon week.** One primary UI + one secondary view (e.g. `/review` or `/brief`) is enough.

---

## D. Factsheet + protocol analysis

**Sources:**  
- Factsheets: site PDF + Zenodo citation doi **10.5281/zenodo.20345207** (PDF p.2) — [download mirror](https://www.oneaquahealth.eu/app/uploads/2026/09/FactSheets_Combined_zenodo_f_citation_F_16092026.pdf)  
- Protocols: doi **10.5281/zenodo.20344421** — [mirror](https://www.oneaquahealth.eu/app/uploads/2026/09/Field-Sampling-protocols-OAH_citation_Final_16092026.pdf)  
- Framework page: combines macros, WQ, habitat with birds, amphibians, adult Diptera **[FACT]**  

### Indicator matrix (from actual materials)

| indicator | measurement type | citizen observable? | photo observable? | equipment? | lab? | domain expertise? | categorical/numeric | units / values | validation rules (protocol/form) | AI assistance potential | AI must NOT attempt | human confirmation | FHIR representation | One Health relevance |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| I Diatoms / teratology | scrape stones → acid clean → microscopy ~400 valves / indices IBD, IPS | No | No (needs micro) | Soft brush, tubes, ethanol | Yes | High taxonomy | Numeric indices + deformity counts | Index scores; counts | CEN EN 13946/14407 | None for values; maybe sample-label OCR | Infer IBD/teratology from stream photo | Expert | `diatomes`, `diatomTratology` in TemporaryOahSystem | Pharma early warning; WFD BQE; HABs |
| II Benthic macroinvertebrates | kick-net 6×1 m; ethanol; lab ID; BMWP etc. | Assisted only if trained | Weak (net contents not ID) | Hand-net 500 µm, waders, preservative | Yes | High | Richness, scores | Biotic scores | CEN EN 27828/16150; 50 m section | Glossaries; photo of *procedure* compliance | Auto BMWP / family ID from phone photo of water | Expert sorter | `#macroinvertebreates` | Water quality ↔ human/animal health narrative |
| III Fish | electrofishing 100 m; ID count | No (permits/safety) | No | Backpack electrofisher | Field+lab | High | Richness, CPUE | Counts / indices | CEN EN 14011 | None | Infer fish community from bank photo | Expert | `#fishes` / `#fish` | Food safety, pathogens, pollutant accumulation |
| IV Amphibians | hand-net 100 m; biometrics; optional pathogen swabs | No without permits | Partial presence only | Net, calliper, gloves; biosecurity | Optional pathogen | High + legal | Counts; disease assays | Counts; Bd/Bsal | **Permits required** **[FACT]** | None for disease | Infer chytrid / species health from photo | Expert+permits | `#amphibians` | Vector control agents; zoonoses |
| V Birds | point count 10 min; Merlin/BirdNET; insectivorous guild | **Yes** (protocol Option 2) | Audio > photo | Smartphone app | No | Medium (guild class) | Species list → guild count | Species counts | Early morning; 10 min; breeding season | Assist ID via Merlin already; flag uncertain | Claim mosquito control efficacy from one walk | Citizen + expert flag | `#birds` | Insectivorous birds ↔ vector control ↔ well-being |
| VI Microbial diversity | eDNA / 16S / metagenomics | No | No | Sterile sampling | Yes | High | Diversity indices | H, S, J | Molecular QA | None | Infer diversity from water colour | Lab | `#microbiomes` | Pathogen biocontrol narrative |
| VII Fecal coliforms | culture / qPCR | No | No | Sterile bottles | Yes | Medium | CFU / gene copies | CFU/100mL etc. | Chain of custody | None | Infer E. coli from photo | Lab | `#coliforms` | Fecal contamination risk |
| VIII Pathogens | culture / qPCR / metagenomics; risk index formulas in factsheet | No | No | Lab | Yes | High | Presence/abundance/risk index | Gene copies; 0–1 risk | Lab QA | None | Diagnose infection risk from photo | Lab + PH | pathogen codes / Specimen | Direct human/animal disease risk |
| IX ARGs | qPCR / metagenomics; selective culture | No | No | Lab | Yes | High | Gene copies | copies/volume | Molecular | None | Claim AMR from turbidity | Lab | (map to microbiome/AMR concepts; IG temporary) | One Health AMR |
| X Diptera adults | overnight CO₂ traps; −80 °C; morph ID; optional pathogen pools | No as casual CS | Trap catch photos weak | BG-Pro, dry ice, powerbank | Yes ID | High | Richness/abundance | Counts | Overnight protocol | Assist morph ID only with expert | Infer West Nile risk from stream selfie | Expert | `#diptera` | Vectors WNV/dengue/chikungunya **[FACT]** policy brief |
| XI Invasive alien plants (riparian) | visual 100 m / 10 checkpoints; % cover; legal class | **Yes** with training | **Yes** (species ID hard) | Notebook; ID guides | No | Medium | Cover %; invasive class | %; categories | 100 m both banks; 5×2 m plots | Species ID assist (Seek-like) + cover estimate assist | Assert allergy/poisoning for individual | Citizen confirm + expert for legal class | `#invasiveOrganisms`; riparian VS | Allergies, toxins, vector habitat |
| Site physico-chem (protocols §2.1) | multiparameter probe | Trained CS possible | No | Probe, GPS, tape, current meter | Field | Low–med | Numeric | °C, mg/L, µS/cm, pH, m/s, cm, m | Annex I ranges sanity | OCR of probe display | Invent DO/pH from photo | Human enters numbers | `#pH` `#dissolvedO2` `#waterTemperature` `#tds` `#conductivity` | WQ ↔ health |
| Hydromorphology (protocols §2.4 / Annex I) | categorical present/extensive/absent | **Yes** | Partial (channelization visible) | Form | No | Low–med | Categorical P/E/A | Flow types, substrates, barriers | Annex I codes | Suggest P/E/A from photo with low confidence | Invent barrier counts blindly | Human | `#morophology` `#hydrology` | Habitat ↔ vectors/predators |
| Macrophytes channel types (protocols §3.4 / Annex I) | A/P/E + native/non-native | **Yes** | **Yes** | Form; photos/video requested | No | Low–med | Categorical | A/P/E; non-native flags | Annex I table; photo/video | Suggest vegetation type | Fine species toxin claims | Human | `ObservationWithCompOah` macrophytes slices | Habitat structure |
| Riparian vegetation (Annex I) | cover bins 1–5 + non-native | **Yes** | **Yes** | Form | No | Low | Ordinal cover | 0–20%…81–100% | Annex I | Assist cover bin | Overstate restoration success | Human | `#riparianVegetation` trees/bushes/herbaceous | Shade, corridors, IAP |
| Foam/colour/smell (code system) | sensory | **Yes** | Colour/foam partial | None | No | Low | Categorical | foam/colour/smell | Consistency rules | Suggest colour class | Chemical ID / toxicity | Human | `#foam` | Pollution cue only |
| Pharmaceuticals (protocols water samples) | lab chemistry | No | No | Bottles, freeze, acid | Yes | High | Concentrations | µg/L etc. | Chain of custody | None | Infer from photo; policy “91% sites” as local claim | Lab | `#pharmaceuticals` | Policy brief 91% **[FACT]** — city-level, not per-photo |
| Land use / GIS buffer | GIS | Analyst | EO optional | GIS | No | Med | % classes | % | 500 m buffer | EO assist | Precise % from one photo | Analyst | `#LandUse` | Urbanization pressure |
| Health / disease prevalence (FHIR HealthMeasure) | epi registries | No (not CS stream visit) | No | Official stats | N/A | High | Rates | per 100k | Official sources only | None | Link one stream visit to hypertension | Epidemiologist | `ObservationHealthMeasureOah` | One Health human pillar |
| Well-being self-report | survey | Yes if ethics | No | Questionnaire | No | Low | Likert etc. | — | Consent | Minimal | Clinical mental-health diagnosis | Subject | HealthMeasure / QuestionnaireResponse | Cultural services |

### AI policy (explicit)

**AI can safely draft (with human confirm):** photo quality / protocol framing flags; plain-language glossary of Annex I terms; suggested A/P/E or cover bin from clear habitat photos (low confidence); assist invasive plant ID candidates; Merlin already handles birds.

**AI can only assist:** duplicate detection; OCR of probe screens; triage priority for ReviewDesk; mapping confirmed fields → DSS/DipteraCAST descriptor checklists.

**AI must never infer:** biotic indices (BMWP, IBD, EFI); pathogen/ARG presence; pharmaceutical concentrations; disease diagnosis or individual infection risk; West Nile/dengue outbreak claims from a single CS visit; electrofishing/Diptera community composition from bank photos; mortality/life-expectancy causal claims beyond citing policy brief at study level.

---

## E. FHIR deep dive

**Repo:** https://github.com/hl7-eu/oah (cloned 21 Sep 2026)  
**CI build:** https://build.fhir.org/ig/hl7-eu/oah (Jina sometimes empty; FSH source is authoritative here)  
**IG status:** draft / experimental temporary code system **[FACT]** `TemporaryOahSystem` `^experimental = true`

### Profiles (from FSH)

| Profile | Key constraints |
|---|---|
| `LocationOah` | `identifier` 1..; `name` 1..; `mode = #instance`; `position` 0..1 but if present lat/long 1..1 |
| `ObservationIndicatorsOah` | **`status = #final`**; `code` from `OahIndicatorsNoHealthOahVs` (preferred); `subject` 1.. → `LocationOah`; `effective[x]` 1..; **`performer` 1..**; `value[x]` CodeableConcept or Quantity; `specimen` → `SpecimenOah` optional |
| `ObservationHealthMeasureOah` | **`status = #final`**; health VS; `subject` → `LocationOah`; `effective[x]` 1..; `focus` → `GroupOah` optional |
| `ObservationWithCompOah` | Parent indicators; `value[x]` 0..0; `component` 1.. with macrophytes / non-native / riparian slices + required VS |
| `SpecimenOah` | `subject` → Location; `collection` 1.. with `collector` PractitionerRole 1..1; `collected[x]` dateTime 1.. |
| `GroupOah` | Definitional person cohorts for health measures |
| `LibraryOah` | Dataset metadata |

**Examples reality check:** Many examples are **Benevento air pollutants** and **disease prevalence** groups—not citizen stream photos. Water examples use Device (Hanna HI98130) and Location identifiers under `https://oneaquahealth.eu/location-id`. Crete Giofyros/Almyros appear in samples—**outside the five hackathon demo cities**, so demo seeding should still prefer Coimbra/Benevento/Ghent/Oslo/Toulouse for narrative even if IG samples elsewhere **[INFERENCE]**.

### Draft vs `Observation.status = #final` tension

**[FACT]** Both OAH Observation profiles **pattern-constrain `status` to `#final`**.  
**[FACT]** FHIR R4 ObservationStatus still includes `registered | preliminary | final | amended | …`; definition of `final` expects completion; Provenance used for signing/release narrative (FHIR Observation status / Provenance docs).

**Standards-backed patterns (do not invent):**

1. **Internal draft domain model → emit FHIR only at finalization** *(recommended for hackathon)*  
   - App workflow states (`draft`, `flagged`, `citizen_confirmed`, `expert_accepted`) live **outside** OAH Observation profiles.  
   - On confirm, map to `ObservationIndicatorsOah` with `status=final`, required `performer`, `effective`, `subject` Location.  
   - Evidence: profile patterns force final; examples all `status = #final`.

2. **`QuestionnaireResponse` for capture, then extract Observations**  
   - QR statuses: `in-progress | completed | amended | …` **[FACT]** FHIR lifecycle.  
   - Fits Annex I form naturally.  
   - Extractor creates final Observations after human completion.  
   - OAH IG does **not** currently define a Questionnaire profile **[FACT]** from repo listing—usable as base FHIR, not OAH-profiled.

3. **`Observation.status = preliminary` during workflow**  
   - Valid in base FHIR; **would violate** current OAH profile pattern if claimed as `ObservationIndicatorsOah`.  
   - Only OK as base Observation or if IG relaxes later **[INFERENCE]**.

4. **Provenance**  
   - **[FACT]** Provenance records agents/entities/activities for authenticity; append-oriented.  
   - Use on finalize: citizen confirm, expert accept, model version used for *suggestions* (as entity), not as ecological truth.

5. **Task**  
   - **[FACT]** Task tracks workflow fulfillment (request review, complete QA).  
   - Appropriate for ReviewDesk queues; not a substitute for Observation content.

6. **Custom metadata / extensions**  
   - OAH extensions today are Library size/record count only **[FACT]**.  
   - Do not invent trust-score extensions as if they were IG; keep flags in app or DocumentReference/Attachment annotations until IG adopts.

**Recommended architecture:** Domain packet + optional QuestionnaireResponse → human confirm → **only then** `Bundle` of `LocationOah` + one/more `ObservationIndicatorsOah` (`status=final`, `performer` populated) + `Provenance`. Never label AI output as OAH-profile Observation.

---

## F. AI feasibility

| Task | In | Out | Model | Reliability | Hallucination | Validation | Human override | Fallback | Cost | Latency | Explainability | Category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Photo protocol QA (blur, not stream, wrong framing) | Image | Flags | CV/heuristics + optional VLM | Medium–high for coarse QA | Medium if VLM narrates ecology | Thresholds; golden set | Yes | Rules-only sharpness/EXIF | Low | Low | Heatmap/reasons | **Essential** for TrustGate |
| Annex I categorical suggest | Image+form | A/P/E suggestions | VLM | Low–medium | High | Constrain to enum | **Mandatory** | Empty form | Med | Med | Show alternatives | **Useful** |
| Glossary / plain language | Term | Explanation | LLM | Medium | Medium | Curated glossary RAG | Edit | Static text from factsheets | Low | Low | Cite factsheet | **Useful** |
| Bird assist | Audio | Species | Merlin (existing) | Productized | Known limits | Expert flag | Yes | Manual list | Low | Low | App confidence | **Useful** (don’t rebuild) |
| Invasive plant ID | Photo | Candidates | CV | Medium | Medium | Local species lists | Yes | Manual | Med | Med | Top-k | **Useful** |
| Composite trust score 0–100 | Mixed | Score | Arbitrary ML | **Low scientific basis** | High | None solid | N/A | **Flags** | — | — | Poor | **Harmful** |
| Auto BMWP / ecological quality class | Photo | Index | VLM | **Very low** | Very high | Impossible casually | Would launder | Refuse | — | — | Fake | **Harmful** |
| Pathogen/AMR/pharma claims | Photo/text | Risk | LLM | Dangerous | Extreme | Lab only | Refuse | Cite policy at study level only | — | — | — | **Harmful** |
| EvidenceBrief free-text | Packet | Narrative | LLM | Medium if templated | High if free | Citation required / refuse | Officer approve | Pure template | Med | Med | Show citations | **Useful** if constrained; else Harmful |
| DipteraCAST prediction | Env descriptors | Taxa | OAH RF/etc. | Trained on 85 sites | Model error ≠ LLM | Domain metrics | Scenario HITL | Don’t call | — | — | Feature importance optional | **Optional** (use theirs) |
| DSS measure recommend | Indicators | Measures | Their DSS | Rules/knowledge | — | Expert | **Required** by DSS copy | Manual DSS | — | — | Trace | **Optional** feeder only |
| Review triage | Flags | Priority | LLM/rules | Medium | Medium | Queue metrics | Yes | FIFO | Low | Low | Reason codes | **Optional** |

**If most “AI assessment” ideas are Optional/Harmful, do not force AI.** Track 3 still allows **validation checks + HITL**; explainable **gates** beat fake vision ecology.

---

## G. Trust architecture

**Trust means:** fitness-for-a-declared-use (e.g. “eligible for FHIR finalize,” “eligible for officer brief,” “eligible for DSS mapping”) expressed as **explicit flags and provenance**, not a mysterious scalar.

| Dimension | Type | Notes |
|---|---|---|
| Protocol completeness (required Annex I fields) | Deterministic | Hard gate |
| Required FHIR fields ready (Location id, effective, performer) | Deterministic | Hard gate before export |
| Image quality / protocol framing | Deterministic heuristics ± AI-assisted | Soft/hard configurable |
| Location/temporal consistency | Deterministic (+ statistical outlier) | City geofence; impossible speeds |
| Measurement ranges | Deterministic | pH, DO, etc. |
| Duplicates | Deterministic/statistical | Same site/time/user |
| Metadata EXIF vs claimed GPS | Deterministic | Flag mismatch |
| Human confirmation | Human-reviewed | Required for authority |
| Expert review | Human-reviewed | When flags say so |
| Source/model provenance | Deterministic ledger | Prompt/model/version if AI used |
| Edit history | Deterministic append-only | Diff AI vs human |

**Prefer quality FLAGS over fake composite scores** unless a published method (e.g. CrowdWater multi-player agreement) is replicated with clear semantics **[FACT]** CrowdWater game improves water-level class accuracy via crowdsourced checks.

---

## H. EvidenceBrief validation

### What an officer needs

Not a chatbot summary. A **decision memo**:

| Candidate content | Keep? | Rule |
|---|---|---|
| Observation summary (confirmed fields) | Yes | Only confirmed |
| Quality status / flags | Yes | Transparent |
| Ecological implication | Yes | Cite factsheet/protocol/WFD language |
| Human-health relevance | Yes | Cite policy brief / factsheet; **no diagnosis** |
| Animal-health relevance | Yes | Vectors, amphibian disease context—cited |
| Evidence/source links | Yes | Mandatory |
| Uncertainty | Yes | Missing fields, CS vs lab grade |
| Next investigation | Yes | Checklist (re-sample, lab, Diptera traps) |
| Responsible authority | Yes | City dept placeholders |
| Historical comparison | Optional | Only if real prior data |
| Generative flourish / alarmism | No | Ban |

**Templates/rules safer than generative AI** for causal language. Policy brief may say degraded streams are *associated with* higher cause-specific mortality **[FACT]**—briefs may **quote association**, must not claim the photographed site caused deaths.

---

## I. Technical depth map (surviving directions)

| Challenge | Why difficult | Why matters | Simplest correct implementation | Production evolution |
|---|---|---|---|---|
| Domain draft ≠ FHIR final | Profile pins `final` + performer | Prevents fake interop | JSON packet + exporter | FHIR server + validation |
| OAH terminology binding | Temporary CS; preferred VS | Judges (Datta) spot fake codes | Use TemporaryOahSystem codes from IG | ConceptMaps to SNOMED/LOINC when exist |
| Protocol-lite subset selection | Most indicators lab | Scientific credibility | Implement Annex I vegetation/hydromorph/sensory only | Expand with kits/partners |
| Flag engine | Easy to overfit AI | Trust | Pure rules + tests | Add calibrated CV |
| Audit/provenance | Easy to skip | FAIR / HITL proof | Append-only event log | FHIR Provenance |
| Evidence templates | Easy to LLM-waffle | Impact 30% | Mustache templates + citations | Controlled NLG |
| Feeder mappings | Unknown DSS I/O | Integration story | Fixture schema + manual map doc | Real adapters |
| Photo storage + PII | Faces, locations | Ethics | Local/object storage; strip EXIF option | Full privacy review |

**Fake complexity to avoid:** microservices mesh, multi-agent swarms, blockchain (judge present ≠ mandate), Isolation Forest on synthetic sensors, Kubernetes for a form.

---

## J. Demo tests (90 seconds)

### TrustGate (+ finalize)
1. Problem: CS rows unusable → officers ignore CS.  
2. User: curator.  
3. Action: submit bad photo (blurry sidewalk) → hard reject; submit Annex I-complete packet → pass.  
4. Difficult capability: deterministic flag report + FHIR Bundle only on confirm.  
5. One Health: refuse pathogen claim; allow foam+riparian flags only.  
6. Output: flags JSON + `Observation` final.  
**Demoable:** strong.

### EvidenceBrief
1. Problem: dashboards without decision narrative.  
2. User: Coimbra officer.  
3. Action: open confirmed packet → generate templated brief.  
4. Difficult capability: citation-enforced generation / refuse.  
5. One Health: vector + IAP sentences from policy brief.  
6. Output: 1-pager PDF/HTML.  
**Demoable:** strongest Impact video; risk looking like Track 2.

### ReviewDesk
1. Problem: contested CS.  
2. User: expert.  
3. Action: accept/edit/reject with reason.  
4. Difficult capability: audit diff.  
5. One Health: reject illegal amphibian claim.  
6. Output: adjudicated packet.  
**Demoable:** good; weaker alone.

### DSS/DipteraCAST feeder
1. Problem: tools need structured inputs.  
2. User: planner.  
3. Action: map confirmed hydromorph/WQ → descriptor pack.  
4. Difficult capability: schema mapping fidelity.  
5. One Health: vector scenario prep.  
6. Output: downloadable pack (+ optional screenshot of their tool).  
**Hard-to-demo** without API; fixture demo acceptable if honest.

### Hardened StreamWitness
1. Problem: inconsistent assessment.  
2. User: citizen.  
3. Action: form + photo → AI *suggestion* on A/P/E → human edits → confirm.  
4. Difficult capability: constrained enums + audit showing human≠AI.  
5. One Health: sentence that riparian loss weakens vector predators (cited).  
6. Output: FHIR.  
**Demoable:** high; **clone risk** high if vision-scoring centered.

---

## K. Failure analysis (pre-mortem)

| Candidate | Why we didn’t place | Mitigation evidence |
|---|---|---|
| TrustGate | “Just forms”; weak AI optics | Show explainable flags + FHIR; cite Track 3 validation language; CrowdWater precedent |
| EvidenceBrief | Generic GPT summary / Track 2 clone | Templates + citations; no map dashboard; Impact 30% story |
| ReviewDesk | No reviewer persona; enterprise CMS vibe | OAH-coded reasons; pair with TrustGate |
| Feeder | Can’t access DSS/DipteraCAST; looks competitive with ENORA | Explicit complement framing; fixtures; ask organizers early |
| Hardened StreamWitness | Identical to 50 Track 3 LLM wrappers; scientifically wrong photo→score | Kill vision scoring; protocol-lite; audit; IG-valid FHIR |
| Kitchen-sink combo | Confused video; unfinished surfaces | One primary thesis; secondary view only |
---

## L. Final shortlist — 3 serious architectures

*Not ranked as THE winner. Not mechanical score-max.*

---

### Finalist 1 — **ConfirmGate** (TrustGate-centered observation lifecycle)

- **Product thesis:** Make citizen/protocol-lite observations *usable* by gating, confirming, and emitting IG-conformant FHIR—quality infrastructure for OAH, not a stream scorer.  
- **Exact user:** CS data curator + citizen submitter (smallest duo).  
- **Exact painful workflow:** Today’s CS/noise → ignored by decision tools.  
- **Core differentiator:** Protocol Annex I vocabulary + flag engine + draft-domain→`status=final` FHIR with Provenance/audit.  
- **Why OAH tools don’t already solve it:** CS captures; maps display; DSS/DipteraCAST need good inputs; IG not operationalized in a HITL app.  
- **Core workflow:** Ingest → flags → citizen confirm → optional expert if flagged → FHIR Bundle.  
- **Technical architecture (conceptual):** Monolith or modular library: `Ingest` → `FlagEngine` → `PacketStore` → `FinalizeExporter`; AI optional behind interface.  
- **AI role:** Optional photo QA / categorical suggestions; **not** required.  
- **Human role:** Authority for values and overrides.  
- **FHIR role:** Export contract only at end.  
- **One Health role:** Enforce non-claim rules; carry Diptera/IAP/habitat fields that *feed* health-relevant tools.  
- **90s demo:** Bad photo rejected; good Annex I packet → final Observation JSON.  
- **Engineering depth:** Conformance + flags + audit (real); not microservice theater.  
- **Hackathon scope:** 1 ingest UI + flag panel + `/fhir` download + 5 cities seed; defer fancy review.  
- **Post-hackathon:** Embed beside CS app; expand indicators with kits.  
- **Win reason:** Solves Track 3 literally with scientific humility; Technical+Feasibility strong; Gora Datta-readable FHIR.  
- **Lose reason:** Looks unflashy vs dashboards; Impact narrative needs One Health sentence discipline.  
- **Unknowns:** CS export/API; who operates QC.  
- **Kill criteria:** Ships composite AI trust score; emits FHIR without human confirm; claims lab indicators from photos.

---

### Finalist 2 — **EvidenceBrief** (officer One Health decision memo)

- **Product thesis:** Translate *confirmed* OAH evidence into a citation-bound officer brief that dashboards don’t provide.  
- **Exact user:** City environment/public-health officer.  
- **Exact painful workflow:** Meeting tomorrow; maps open; no defensible paragraph.  
- **Core differentiator:** Template engine grounded in policy brief + factsheets; refuse missing evidence.  
- **Why OAH tools don’t solve it:** Dashboards/Resilience Map visualize; Policy Brief is static PDF; no per-site actionable memo workflow.  
- **Core workflow:** Select city/site packet (fixtures OK) → brief → human approve → share/PDF.  
- **Technical architecture:** Read-only packet store + template renderer (+ optional constrained LLM filler) + citation registry.  
- **AI role:** Optional slot-filling; templates essential.  
- **Human role:** Approval authority.  
- **FHIR role:** Optional input Observations; not mandatory if packet JSON provenanced.  
- **One Health role:** Core—human/animal/ecosystem sentences with uncertainty.  
- **90s demo:** Coimbra brief with pharma association cited at study level + local confirmed riparian flags.  
- **Engineering depth:** Knowledge constraints / citation integrity (real).  
- **Hackathon scope:** One brief UI + 2–3 fixture packets; no rebuild of maps.  
- **Post-hackathon:** Connect live hub APIs.  
- **Win reason:** Impact 30% alignment; excellent video.  
- **Lose reason:** Track 2 optics; “content not software”; thin Technical if only GPT.  
- **Unknowns:** Officer cadence; who may publish claims.  
- **Kill criteria:** Ungrounded causal claims; alarmism; dashboard clone.

---

### Finalist 3 — **Hardened StreamWitness (narrow client)** *or* **Descriptor Feeder** (pick one orientation)

Present as **two mutually exclusive orientations** under one finalist slot—choose before build.

#### 3A. Narrow StreamWitness (Track 3 client)
- **Thesis:** Best-in-class HITL client for **Annex I-sortable** observations with visible DRAFT→confirm→FHIR.  
- **User:** Citizen volunteer.  
- **Pain:** Jargon + inconsistent reports.  
- **Differentiator:** Only protocol-lite enums + audit showing human edits over AI; IG-valid export.  
- **Why not CS app alone:** Public FHIR/audit/DRAFT lifecycle not exposed **[UNKNOWN]** internals; Track 3 asks AI-supported assessment with HITL.  
- **Workflow:** Upload/form → optional AI suggest → confirm → flags → FHIR.  
- **AI:** Assist only.  
- **Human:** Authority.  
- **FHIR:** End state.  
- **One Health:** Closing sentence + fields that matter to vectors/habitat.  
- **Demo:** Classic photo→confirm→JSON—but narration stresses *what AI was forbidden to do*.  
- **Depth:** Constraint UX + conformance.  
- **Scope:** `/upload` `/review` `/fhir` as already sketched locally—**re-scope fields** to Annex I.  
- **Win:** Clear Track 3; Feasibility.  
- **Lose:** Clone density if vision-scoring returns.  
- **Kill:** Auto stream score; lab indicator invention.

#### 3B. DipteraCAST/DSS Descriptor Packager (Track 3/6/7 bridge)
- **Thesis:** Package confirmed site characterization into inputs official AI/DSS already understand.  
- **User:** Practitioner/planner.  
- **Pain:** Tools starved of structured CS.  
- **Differentiator:** Complement ENORA/DSS; “extend don’t rebuild.”  
- **Why not already:** No public packaging path **[UNKNOWN]** API.  
- **Workflow:** Confirmed fields → mapping → pack → human checks → download/simulate.  
- **AI:** Theirs, not yours.  
- **Human:** Descriptor truth.  
- **FHIR:** Optional upstream.  
- **One Health:** Vector surveillance prep.  
- **Demo:** Hard without access—fixture honesty required.  
- **Win:** Maximal ecosystem alignment; Innovation as bridge.  
- **Lose:** Partner dependency; judge conflict if misframed.  
- **Kill:** “We predict mosquitoes” marketing.

**Recommendation between 3A/3B:** Default **3A** for solo deadline control unless organizers provide DipteraCAST/DSS I/O within 48h **[INFERENCE]**.

---

## M. Unknowns

1. CS app field schema, photo rules, export/API, current QC process.  
2. Public/hackathon access to DSS and DipteraCAST input schemas.  
3. Who (role) reviews CS data operationally today—if nobody, ReviewDesk weakens.  
4. City officer decision cadence and acceptable claim language.  
5. Ethics constraints for well-being / health measure demos.  
6. Authoritative ConceptMaps from TemporaryOahSystem to international codes.  
7. Whether IG will relax `status=final` pattern before judging (unlikely).  
8. Peer submission gallery (unpublished)—clone density unknown.  
9. Multilingual factsheet availability for 5 cities.  
10. Exact relationship between Zenodo versions `20345206` vs `20345207`.

---

## N. Questions requiring organizer / domain-expert answers

1. Provide CS app **sample export** or field dictionary for hackathon teams.  
2. Is there an official **citizen-safe subset** of indicators distinct from lab factsheets?  
3. DSS: any API, file schema, or sanctioned sample inputs?  
4. DipteraCAST: descriptor template file + permission to demo “prep only”?  
5. Preferred FHIR draft pattern: domain-only vs QuestionnaireResponse vs preliminary Observations?  
6. May demos use **synthetic** site data labeled clearly, or must hit live hubs?  
7. For EvidenceBrief, what claims are **out of bounds** for non-clinical apps?  
8. Track preference politics: will pure FHIR tooling be scored under Track 3 Impact or pushed to Track 7?

---

## Source index (primary used)

- Devpost home + rules: https://oneaquahealth-ieee-hackathon.devpost.com/ · `/rules`  
- OAH solutions, DSS, framework, DipteraCAST article, policy brief PDF  
- Factsheets PDF (Zenodo citation 20345207) + Protocols PDF (20344421)  
- GitHub `hl7-eu/oah` FSH profiles/terminologies/examples  
- HL7 FHIR R4 Observation status, Provenance, Task, lifecycle  
- FreshWater Watch; CrowdWater; CrowdWater game PLOS One 2019  
- Competitors noted: iNaturalist/Seek (species ID ≠ OAH assessment)

---

**DECISION REQUIRED - DO NOT IMPLEMENT**

Humans must decide **before any architecture/code**:

1. **Primary finalist:** ConfirmGate (1) vs EvidenceBrief (2) vs Narrow StreamWitness 3A vs Descriptor Feeder 3B.  
2. **Track number:** Track 3 default; switch to Track 7 only if FHIR tooling becomes the product thesis; Track 2 only if EvidenceBrief is primary *and* organizers agree.  
3. **Indicator scope:** Commit to **protocols Annex I categorical + sensory (+ optional birds via Merlin)** — explicitly **exclude** lab factsheet indicators from AI draft scope.  
4. **AI posture:** Rules/flags-first vs vision-suggest-on-enums; **ban** composite trust scores and photo→biotic index.  
5. **Persona scope:** Citizen+system only vs add reviewer vs add officer brief view (max one secondary persona UI).  
6. **FHIR draft pattern:** Approve **domain packet → final Observation only** (recommended) vs QuestionnaireResponse path.  
7. **EvidenceBrief:** Separate product vs optional output module of ConfirmGate (recommended if choosing 1).  
8. **Partner dependency:** Proceed without DSS/DipteraCAST APIs (fixtures) vs block on organizer access.  
9. **Kill switches:** Pre-agree kill criteria in Section L; if violated in prototype, scrap rather than submit.

*End of validation report.*
